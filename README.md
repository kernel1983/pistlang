# Pist

**Pist** (pistlang) is a programming language inspired by Python and Lisp. It uses Lisp-like prefix notation with brackets `[...]` and compiles to Python.

```
print                    →  print(
    [square 10]          →      square(10)
                         →  )
```

## Design Process

Pist was born from a simple conversation with GPT — no compiler expertise needed, just an idea and iterative prompting.

The core insight: writing a compiler doesn't have to be hard if the target is another high-level language. Instead of building a full AST, type system, and code generator, pist directly emits Python source code.

The design evolved through prompt-and-correct cycles:

1. **Start small** — a single `tokenize_expr` function that turns `[foo a b]` into `foo(a,b)`
2. **Add indentation** — block-style calls (`print\n    [foo]`) as syntax sugar over brackets
3. **Add control flow** — `fn`, `if`, `while`, `return` mapped to Python statements
4. **Add operators** — prefix `[* x x]` becomes infix `x * x`
5. **Add lambdas** — `[fn [x] * x x]` becomes `lambda x: x * x`, enabling `map`/`filter`
6. **Nest recursively** — block calls can nest, giving `print(list(filter(...)))`

Each feature was tested with real `.pi` files and iterated until the generated Python was correct.

## Design Philosophy

Pist deliberately does not chase Lisp's 7 foundational operators (`car`, `cdr`, `cons`, `atom`, `eq`, `quote`, `cond`) or the pair-list-as-everything data model. Python already has excellent data structures — dicts, lists, tuples, sets — and C already has excellent static types. There is nothing to prove there.

Instead, pist takes two things from Lisp that actually matter:

1. **Stable syntax** — every expression looks the same: `[verb arg arg ...]`. Python adds new syntactic sugar every release (match/case, walrus `:=`, type union `X | Y`, etc.). Pist will never do that. The syntax you learn on day one is what the language will look like forever.
2. **Code is data** — a pist program is a string of `[...]` expressions, recursively structured. You can build, transform, and emit pist programs programmatically because the syntax has no hidden rules, no special forms disguised as keywords, and no context-sensitive parsing.

The dynamic/static boundary is handed off cleanly to Python and C. Pist code stays pure, minimal, and predictable.

## Bracket Design

Brackets `[...]` are used for all function calls and prefix expressions, which has a cascading effect on the rest of the syntax.

### map, not list comprehension

Python's list comprehension `[x*2 for x in lst]` is a special syntax form with its own parser rules. Pist does not have comprehensions — use `map` with a lambda instead:

```
[map [fn [x] * x 2] lst]
    → map(lambda x: x * 2, lst)
```

This is not a limitation. Every comprehension introduces a new grammar rule; `map` is just a function call. The same mechanism works for `filter`, `reduce`, or any other higher-order function.

### Literal constructors

Since brackets are reserved for function calls, there is no `[1, 2, 3]` list literal. Instead, use explicit constructors:

```
l = [list (1, 2, 3)]     → l = list((1, 2, 3))
s = [set (1, 2, 3)]      → s = set((1, 2, 3))
```

Tuples and dicts retain their familiar syntax because they do not conflict with brackets:

```
t = (1, 2, 3)            → t = (1, 2, 3)
d = {1: 2, 3: 4}         → d = {1: 2, 3: 4}
```

### Tribute

The choice of `[...]` over `(...)` is intentional. Parentheses are overloaded in most languages (grouping, tuples, function calls). Brackets are visually cleaner — no shift key required on most keyboards — and they pay tribute to two traditions: **Logo**, which used brackets for list construction, and **Objective-C**, which used brackets for message passing `[receiver message]`.

## Key Features

### Prefix notation with brackets

```
[print "hello"]           →  print("hello")
[+ 1 2]                   →  1 + 2
[list (1, 2, 3)]          →  list((1, 2, 3))
```

### Indentation-based block calls

```
print
    [square 10]
    [square 20]
```
→ `print(square(10), square(20))`

### Functions and control flow

```
fn fib [n]
    if [< n 2]
        return n
    return [+ [fib [- n 1]] [fib [- n 2]]]
```

### Anonymous functions (lambdas)

```
[map [fn [x] * x x] nums]
```
→ `map(lambda x: x * x, nums)`

### Nested block calls

```
print
    list
        [filter [fn [x] [> x 0]] nums]
```
→ `print(list(filter(lambda x: x > 0, nums)))`

## Usage

```bash
python pistc.py program.pi   # prints compiled Python
python pistc.py program.pi | python   # compile and run
```

## How it works

The entire compiler is a single file (`pistc.py`, ~200 lines) with no dependencies.

A traditional compiler pipeline looks like:

```
lexer → parser (grammar rules, AST types) → semantic analysis → codegen
```

Pist eliminates the parser and AST layer entirely. Because `[...]` is the *only* syntax construct, the token list naturally forms a tree — no grammar rules, no parsing strategies, no AST node types needed.

```
split_tokens → tokenize_expr (recursive dispatch)
```

- **`split_tokens`** splits by whitespace while tracking bracket depth — no keyword/operator awareness needed
- **`tokenize_expr`** dispatches on the first token: `fn` → lambda, operator → infix, anything else → function call
- **`is_block_call`** / **`_compile_block_call`** handle indentation-based calls recursively
- **`convert_statement`** maps statement-level forms (`fn`, `if`, `while`, `return`, assignment) to Python

The result is what looks like a 200-line prototype, but actually the pipeline can't shrink any further — every line is essential, because the simplicity comes from the data model, not from cutting corners.

## License

MIT
