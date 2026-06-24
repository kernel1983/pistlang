# pistc.py

import re
import sys


def tokenize_expr(s):
    """
    简单解析:
    [foo a b] -> foo(a,b)
    """
    assert s.startswith("[") and s.endswith("]")

    inner = s[1:-1].strip()

    tokens = split_tokens(inner)

    if not tokens:
        return ""

    fn = tokens[0]
    args = tokens[1:]

    if fn in {"+", "-", "*", "/", "%", ">", "<", "=="}:
        if len(args) == 2:
            return f"{args[0]} {fn} {args[1]}"

    return f"{fn}({', '.join(convert_token(x) for x in args)})"


def split_tokens(s):
    result = []
    current = ""
    depth = 0

    for c in s:
        if c in "[({":
            depth += 1

        if c in "])}":
            depth -= 1

        if c == " " and depth == 0:
            if current:
                result.append(current)
                current = ""
        else:
            current += c

    if current:
        result.append(current)

    return result


def convert_token(x):
    if x.startswith("["):
        return tokenize_expr(x)

    if x.startswith("("):
        return x

    if x.startswith("{"):
        return x

    return x


def parse_line(line):
    indent = len(line) - len(line.lstrip())
    text = line.strip()

    return indent, text


def compile_pist(source):
    output = []
    stack = [0]

    lines = source.splitlines()

    for raw in lines:
        if not raw.strip():
            continue

        indent, text = parse_line(raw)

        while stack and indent < stack[-1]:
            stack.pop()
            output.append(" " * (len(stack)-1)*4)

        py = convert_statement(text)

        output.append(" " * (len(stack)-1)*4 + py)

        if opens_block(text):
            stack.append(indent + 4)

    return "\n".join(output)


def opens_block(text):
    return (
        text.startswith("fn ")
        or text.startswith("if ")
        or text.startswith("while ")
        or text in ("else",)
    )


def convert_statement(text):

    # function
    if text.startswith("fn "):
        name, args = text[3:].split("[")
        args = args.rstrip("]")
        return f"def {name.strip()}({args}):"

    # if
    if text.startswith("if "):
        expr = text[3:]
        return f"if {convert_token(expr)}:"

    # while
    if text.startswith("while "):
        expr = text[6:]
        return f"while {convert_token(expr)}:"

    if text == "else":
        return "else:"

    # return
    if text.startswith("return "):
        return "return " + convert_token(text[7:])

    # assignment
    if "=" in text and not text.startswith("["):
        a, b = text.split("=", 1)
        return f"{a.strip()} = {convert_token(b.strip())}"

    # expression statement
    if text.startswith("["):
        return convert_token(text)

    return text


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        pist = f.read()

    python = compile_pist(pist)

    print(python)