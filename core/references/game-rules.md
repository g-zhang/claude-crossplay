# NYT Crossplay rules reference

Read this file before manually checking a reported score or writing strategic
notes. The solver is the source of truth for move generation and scoring; this
reference explains the values used by the solver.

## Tile values

| Points | Letters |
|--------|---------|
| 1 | A, E, I, N, O, R, S, T |
| 2 | D, L, U |
| 3 | C, H, M, P |
| 4 | B, F, G, Y |
| 5 | W |
| 6 | K, V |
| 8 | X |
| 10 | J, Q, Z |

## Tile distribution

There are 100 tiles, including three blanks. Each player starts with seven.

| Count | Letters |
|-------|---------|
| 12 | E |
| 9 | A |
| 8 | I, O |
| 6 | R, T |
| 5 | N, S |
| 4 | D, L |
| 3 | G, H, U, BLANK |
| 2 | B, C, F, M, P, V, W, Y |
| 1 | J, K, Q, X, Z |

## Premium layout

Coordinates are zero-based `(row, column)`.

| Type | Positions |
|------|-----------|
| 3W | (0,3) (0,11) (3,0) (3,14) (11,0) (11,14) (14,3) (14,11) |
| 2W | (1,1) (1,13) (3,7) (7,3) (7,11) (11,7) (13,1) (13,13) |
| 3L | (0,0) (0,14) (1,6) (1,8) (4,5) (4,9) (5,4) (5,10) (6,1) (6,13) (8,1) (8,13) (9,4) (9,10) (10,5) (10,9) (13,6) (13,8) (14,0) (14,14) |
| 2L | (0,7) (2,4) (2,10) (3,3) (3,11) (4,2) (4,12) (5,7) (7,0) (7,5) (7,9) (7,14) (9,7) (10,2) (10,12) (11,3) (11,11) (12,4) (12,10) (14,7) |

The center `(7,7)` has no premium.

## Scoring

- Letter premiums multiply only the newly placed tile on that square.
- Word premiums multiply the whole word. Multiple word premiums stack.
- Premiums do not apply again to existing tiles.
- Newly placed tiles apply their premiums to both the main word and any cross
  word they form.
- Playing all seven rack tiles earns a 40-point bonus.
- A blank always scores zero, including on a letter premium.

## Endgame

- The game ends when the bag is empty and each player has had one more turn.
- Remaining tiles do not incur a penalty.
- Near the end, maximize points rather than sacrificing score merely to empty
  the rack.
