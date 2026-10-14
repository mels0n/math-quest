# 0004. Check answers in isolated worker processes

- Status: accepted
- Date: 2026-10-13

## Context
Checking an answer runs SymPy on text a learner typed. Even after the LaTeX parser
(ADR-0002) has bounded the input, simplification and comparison can take
unpredictable time, and SymPy work cannot be interrupted from inside the process
that runs it. A single slow or adversarial answer must not stall the web server or
other learners, and every answer needs a bounded response time.

## Decision
Answers are checked in a small pool of worker processes (`CheckerPool` in
`engine/checker/bounded.py`).

- Each check has a hard limit of 2 seconds. When it is exceeded, the pool terminates
  its worker processes, replaces the pool, and reports the answer as unreadable.
  Termination is the only reliable way to stop SymPy work.
- The pool has two workers and starts them with `forkserver` where the platform has
  it (`spawn` otherwise), so workers are never forked from the threaded server.
- The pool is warmed before it is used: every worker is started and imports SymPy
  and the checker. Import cost therefore never counts against the 2 second budget of
  a learner's answer. Warm-up failure is logged and does not stop the app.
- A broken pool is replaced and the check retried once. Any other worker failure is
  logged and reported as unreadable.
- Input is bounded before it reaches SymPy by the own parser: 200 characters, nesting
  depth 20, literal exponents of at most 100. Longer input is unreadable without
  reaching a worker.

## Alternatives rejected
- **In-process with signal or thread timeouts.** Signals only fire between Python
  bytecodes and not at all off the main thread, and a thread cannot be killed, so a
  runaway computation keeps consuming CPU after the caller gave up.
- **Async-only.** Awaiting a CPU-bound computation does not make it interruptible and
  would block the event loop for every learner while it runs.
- **A separate checker service.** It solves isolation but adds a deployment unit, a
  network hop and a failure mode for a workload that a local process pool bounds
  just as well at this scale.

## Consequences
A pathological answer costs at most 2 seconds and a pool restart, and it affects only
the answer that triggered it. The price is process management in the codebase and a
cold start of a few seconds at boot, which the warm-up pays before traffic arrives.
The two-worker size caps concurrent checks per replica; raising it is a one-line
change if measurements call for it.
