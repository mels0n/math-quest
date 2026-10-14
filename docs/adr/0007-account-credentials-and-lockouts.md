# 0007. Low-security credentials with narrow lockouts

- Status: accepted
- Date: 2026-10-13

## Context
Players are children, often on a shared family device. The product must not collect
personal data, so there is no email address, real name or age anywhere in the schema.
Credentials must be easy for a young child to enter and recover, which makes them
weak by design: a 4 digit PIN or a sequence of 4 pictures chosen from 12, and a
recovery word. The design has to limit what an attacker can do with guesses, without
letting a guesser lock the real child out of their own account.

## Decision
- A player has a nickname and either a 4 digit PIN or a picture password (4 picture
  ids, each 0 to 11). Signup also requires a grown-up's signup word, stored hashed.
- Signup issues one recovery word drawn from a list of about 1,100 words. Recovery
  replaces the credential, rotates the recovery word (the new word always differs
  from the old one) and signs out every other device.
- Secrets are hashed with argon2id (memory 19,456 KiB, time cost 2, parallelism 1).
  An unknown nickname still pays for one verification, so nickname existence is not
  revealed by timing.
- Failures are counted per (player, device key, IP bucket). Five failures within 60
  seconds lock that triple for 30 minutes. A second counter per (player, IP bucket)
  across all device keys locks the pair after 15 failures in 10 minutes, which stops
  an attacker from rotating device keys. Other devices, other addresses and other
  players are unaffected. Lockouts are never account-wide.
- Recovery guesses also count per player across every address: ten failures in a day
  disable recovery for that player for the next day. PIN and picture login stay
  available.
- Attempts for one player are serialized by a row lock taken with a 3 second wait
  limit. A wait that runs out is reported as "locked, retry in 5 seconds". The lock is
  a non-key lock, so inserts into the player's child tables are not blocked, and the
  lock timeout is reset to the default afterwards.

## Alternatives rejected
- **Passwords and email.** Better security, but it requires personal data the product
  deliberately does not hold, and it is unusable for young children.
- **Account-wide lockouts.** Anyone who knows a nickname could lock the child out
  indefinitely. Locking only the guesser's device and address bounds the guesser, not
  the owner.
- **Two-word recovery phrases.** Stronger, but harder for a child to write down and
  type. The per-player daily cap on recovery guesses makes the single word adequate
  for the threat of a classmate guessing.
- **Unserialized attempts.** Parallel guesses would all read the same failure count
  and slip past the limit. Serializing per player makes the limit exact.

## Consequences
The credentials protect game progress, not anything sensitive, and the documentation
says so. A determined attacker can still try a small number of guesses per address
per window, and a child's own mistakes lock only their current device for a while.
Hashing and the per-player lock make login slower than a bare lookup, which is the
point.
