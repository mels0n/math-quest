# 0002. Parse learner LaTeX with our own parser

- Status: accepted
- Date: 2026-10-13

## Context
Learners enter answers through MathLive, which produces LaTeX. The checker must
decide whether an answer is mathematically correct and also whether it has the
required form: a fraction in lowest terms, a mixed number, a simplified radical, a
factored or expanded polynomial. Form checks need the structure of what the learner
typed, not only its value.

SymPy ships `parse_latex`, which is the obvious choice. It does not fit:

- It evaluates while parsing, so `\frac{6}{8}` and `\frac{3}{4}` come back as the
  same object and the unsimplified form is lost.
- It reads the mixed number `1\frac{1}{2}` as the fraction 1/2, dropping the whole
  part.
- Turning evaluation off with `evaluate=False` does not repair this; that mode
  fails on such input.
- Its parsing path is not designed for hostile input from untrusted users.

## Decision
The engine contains a small tokenizer and Pratt parser for the LaTeX subset that
MathLive produces for this game. It builds an unevaluated syntax tree that records
how the answer was written (fraction versus slash, explicit versus implied
multiplication, parenthesized groups, mixed numbers). Input is bounded in length,
nesting depth and exponent size. Anything outside the supported subset is reported
as unreadable rather than guessed at.

A separate bridge converts the tree to SymPy expressions for value comparison. Form
checks run on the tree. Learner input is never passed to `eval`, `sympify` or
`parse_expr`.

## Alternatives rejected
- **`sympy.parsing.latex.parse_latex`.** Rejected for the evaluation and mixed
  number behavior above, which make form checking impossible.
- **Preprocess the string, then use `sympify`.** Evaluates untrusted text and still
  loses structure.
- **Make MathLive emit a structured format instead of LaTeX.** Ties the checker to
  one editor's internal format and does not help for typed fallbacks.

## Consequences
The project owns a parser and must test it thoroughly, including property tests and
adversarial input. In return, form checks are exact, behavior on malformed input is
defined, and the supported syntax is documented in one place.
