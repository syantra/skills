# Workfront proof viewer API notes

Captured from the proof viewer's own network traffic (October 2026). None of this is documented by Adobe, so expect changes. If calls start failing, re-capture with `tools/capture_traffic.py` in this repo.

## Review URL

```
https://TENANT.my.workfront.adobe.com/proof/review/<hex>-<proofToken>-<suffix>?tcmsTenantId=<tenant>#token:<proofToken>,comment:3/
```

- Proof token: the middle part of the last path segment, or `token:` in the fragment. Each version has its own token.
- `tcmsTenantId`: sent back as the `tcmstenantid` header.
- `comment:N`: the comment the link opens.

## RPC

`POST https://us.my.workfront.com/proof/rpc/index.php`, header `Content-Type: application/x-www-form-urlencoded` but with a **JSON** body (a real form body gets HTTP 400).

| Method | Params | Returns |
|---|---|---|
| `startup` | `token`, `proofingCode: ""` | `sessionId`, `proof` (name, version, versions, pages, `isLoginRequired`, `sourceFiles[]`), `recipient` (null when anonymous), `permissions` (bitmasks), `urls` |
| `comments` | `sessionId` | `items[]` comments of this version |
| `versions` | `sessionId`, `only_processed: false` | `items[]` one per version, each with its own `token` |
| `recipients` | `sessionId` | stages, each with reviewer `items[]` (`name`, `email`, `roleName`, `decision`, `isMe`) |

- Versions: `startup` with a version's own `token` opens that version; its comments, pages and reviewers are separate. `commentsCount` in `versions` can be one lower than what `comments` returns (seen on v4: 6 vs 7, one comment with empty text).
- Decisions: `proof.decision` is the overall outcome and a stage's `decision` is that stage's outcome (null until an approver decides); each reviewer has their own. Values are codes such as `decisionApprovedWithChanges`, `decisionNotRelevant`, `decisionPending`. "Not relevant" with `decisionAt: 0` means the approver didn't need to decide. Roles: `roleReviewer`, `roleReviewerApprover`. Stages can be added while a proof is live (a `Dev` stage appeared on 2026-10-07).
| `list_actions` | `sessionId` | comment action labels |

`startup` works without login when `proof.isLoginRequired` is false. A bad session gets HTTP 401.

Write methods, taken from the viewer's own code (`assets.proofhq.com/nativeviewer/1.109.5/`):

| Method | Params |
|---|---|
| `add_reply` | `sessionId`, `commentId` (the comment's `id`, not `number`), `text`, `notifyRecipients: []`, `attachmentIds: []` |
| `resolve_comment` / `unresolve_comment` | `sessionId`, `commentId` |
| `delete_reply` | `sessionId`, `replyId` |
| also present | `add_comment`, `update_comment`, `delete_comment`, `mark_as_read`, `set_comment_action`, `reserve_comment` |

## Reviewer identity

Writes need a session tied to a reviewer. Signing in through the viewer (`check_email`, then `sign_in` with email and password) makes the viewer rewrite the fragment to `#proof:<proofingCode>,token:<token>,...`. `startup` with that `proofingCode` returns `recipient` (name, `roleName` such as `roleReviewerApprover`). The code is not kept in browser storage, so `scripts/login.py` reads it from the address bar after sign-in and saves it to `~/.config/workfront-proof/codes.json`. Treat the code as a credential.

## Comment fields

`number, page, pages[], text, author, created, isResolved, actionId, actionName, replies[], attachments[], drawings[], pinPoint, pins{page: point}, metadata.pageSizes, permissions (bitmask), captureUrl (null in practice)`.

- `text` is HTML: mentions are `<a class="userlink" href="<email>">Name</a>`, quotes come as entities (`&#039;`).
- `actionName` is a label from `list_actions` (per account, e.g. `STET`, `In Progress`), set with `set_comment_action`.
- `pages[]`: a comment can cover several pages; `pins` and `metadata.pageSizes` then have one entry per page, and each drawing has its own `page`.
- `replies[]` are one level deep (no parent id): `number` (shown as `<comment>.<number>`), `type` (1 text reply, 2 action applied: empty `text`, `actionName` set), `author`, `text`, `permissions`.

`drawings[]`: `type` (`RECTANGLE`, `ARROW`), `page` (1-based), `color`, `points[]`, plus viewer-scaled `x, y, width, height`.

## Markup coordinates

`metadata.pageSizes[page] = {WIDTH, HEIGHT, PHQSCALE}` gives the page size in pixels. Drawing points and pins are measured from the page centre, in units of 1/PHQSCALE, with y pointing down:

```
px = point.x * PHQSCALE + WIDTH / 2
py = point.y * PHQSCALE + HEIGHT / 2
```

Checked on a real comment: `506.125 * 4 + 9215 / 2 = 6632`, matching the viewer's `x = 1658` times 4.

## Files

- `proof.sourceFiles[]`: `{name, mime, size, pagesFrom, pagesTo, url}`. `url` is a short-lived signed link to the original upload. Proof page N maps to page `N - pagesFrom` of the file that covers it. PDF pages have the same proportions as `pageSizes`, so pixel boxes scale straight onto PDF points.
- Page images also exist as Zoomify tiles on `cdn.proofhq.com/<hash>/<token>/temp/converted/<page>/TileGroup0/z-x-y.jpg` (signed per page). Not used, because the source file is simpler.

## Documented REST API (not used)

Adobe also publishes a ProofHQ REST API (https://rest.proofhq.com/, OpenAPI 1.0.56) with `sessionId`, JWT or `WF-Service-Token` auth. The viewer doesn't use it, and we have no way to get those credentials, so the skill uses the RPC above.
