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

    if fn == "fn" and args:
        params = args[0]
        if params.startswith("[") and params.endswith("]"):
            params = ", ".join(p for p in params[1:-1].split())
        body_tokens = args[1:]
        if len(body_tokens) == 3 and body_tokens[0] in {"+", "-", "*", "/", "%", ">", "<", "=="}:
            body = f"{convert_token(body_tokens[1])} {body_tokens[0]} {convert_token(body_tokens[2])}"
        elif len(body_tokens) == 1:
            body = convert_token(body_tokens[0])
        else:
            body = f"{body_tokens[0]}({', '.join(convert_token(x) for x in body_tokens[1:])})"
        return f"lambda {params}: {body}"

    if fn in {"+", "-", "*", "/", "%", ">", "<", "=="}:
        if len(args) == 2:
            return f"{convert_token(args[0])} {fn} {convert_token(args[1])}"

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


def _compile_block_call(text, lines, i, indent):
    """Compile a block call and its (possibly nested) children.
    Returns (python_code_string, next_line_index)."""
    children_py = []
    j = i + 1
    while j < len(lines):
        child_raw = lines[j]
        if not child_raw.strip():
            j += 1
            continue
        child_indent, child_text = parse_line(child_raw)
        if child_indent <= indent:
            break
        if is_block_call(child_text, lines, j, child_indent):
            child_code, j = _compile_block_call(child_text, lines, j, child_indent)
            children_py.append(child_code)
        else:
            children_py.append(convert_token(child_text))
            j += 1
    args = ", ".join(children_py)
    return f"{text}({args})", j


def compile_pist(source):
    output = []
    stack = [0]

    lines = source.splitlines()

    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue

        indent, text = parse_line(raw)

        while stack and indent < stack[-1]:
            stack.pop()
            output.append(" " * (len(stack)-1)*4)

        if is_block_call(text, lines, i, indent):
            py, i = _compile_block_call(text, lines, i, indent)
            output.append(" " * (len(stack)-1)*4 + py)
            continue

        py = convert_statement(text)

        output.append(" " * (len(stack)-1)*4 + py)

        if opens_block(text):
            stack.append(indent + 4)

        i += 1

    return "\n".join(output)


def is_block_call(text, lines, i, indent):
    if not text.isidentifier() or text in {"else", "try", "except", "finally"}:
        return False
    j = i + 1
    while j < len(lines):
        if not lines[j].strip():
            j += 1
            continue
        child_indent, _ = parse_line(lines[j])
        return child_indent > indent
    return False


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

    if "[" in text:
        return convert_token(f"[{text}]")

    return text


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        pist = f.read()

    python = compile_pist(pist)

    print(python)