"""
Pist → Python AST → bytecode compiler.

Usage:
    python pistc_ast.py test.pi        # compile and run
    python pistc_ast.py test.pi -d     # compile, run, and disassemble
"""

import ast
import sys

# ---- Operator maps ----

_BINOPS = {
    "+": ast.Add(),
    "-": ast.Sub(),
    "*": ast.Mult(),
    "/": ast.Div(),
    "%": ast.Mod(),
}

_CMPOPS = {
    ">": ast.Gt(),
    "<": ast.Lt(),
    "==": ast.Eq(),
    ">=": ast.GtE(),
    "<=": ast.LtE(),
    "!=": ast.NotEq(),
}

# ---- Tokenization ----


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


_KEYWORDS = {"True", "False", "None"}


def to_expr(token):
    """Convert a token string to an ast.expr node."""
    s = token.strip()
    if s.startswith("["):
        return bracket_expr(s)
    if s.startswith("(") or s.startswith("{") or s.startswith("\"") or s.startswith("'"):
        return ast.parse(s, mode="eval").body
    if s in _KEYWORDS:
        return ast.Constant(value={"True": True, "False": False, "None": None}[s])
    for t in (int, float):
        try:
            return ast.Constant(value=t(s))
        except ValueError:
            pass
    return ast.Name(id=s, ctx=ast.Load())


def _body_tokens_to_expr(tokens):
    """Convert raw body tokens (e.g. the body of a lambda) to an ast.expr."""
    if len(tokens) == 1:
        return to_expr(tokens[0])
    if len(tokens) == 3 and tokens[0] in _BINOPS:
        return ast.BinOp(
            left=to_expr(tokens[1]), op=_BINOPS[tokens[0]], right=to_expr(tokens[2])
        )
    if len(tokens) == 3 and tokens[0] in _CMPOPS:
        return ast.Compare(
            left=to_expr(tokens[1]),
            ops=[_CMPOPS[tokens[0]]],
            comparators=[to_expr(tokens[2])],
        )
    return ast.Call(
        func=to_expr(tokens[0]),
        args=[to_expr(t) for t in tokens[1:]],
        keywords=[],
    )


def bracket_expr(s):
    """Convert [fn [x] body], [op a b], [foo a b] to an ast.expr."""
    inner = s[1:-1].strip()
    tokens = split_tokens(inner)
    if not tokens:
        return ast.Constant(value=None)

    fn, *args = tokens

    if fn == "fn":
        return _lambda_expr(args)
    if fn in _BINOPS and len(args) == 2:
        return ast.BinOp(
            left=to_expr(args[0]), op=_BINOPS[fn], right=to_expr(args[1])
        )
    if fn in _CMPOPS and len(args) == 2:
        return ast.Compare(
            left=to_expr(args[0]),
            ops=[_CMPOPS[fn]],
            comparators=[to_expr(args[1])],
        )
    return ast.Call(
        func=to_expr(fn), args=[to_expr(a) for a in args], keywords=[]
    )


def _lambda_expr(args):
    """Convert the args of a [fn ...] form into an ast.Lambda."""
    params_text = args[0]
    if params_text.startswith("["):
        param_names = params_text[1:-1].split()
    else:
        param_names = [params_text]
    params = [ast.arg(arg=p, annotation=None) for p in param_names]
    body = _body_tokens_to_expr(args[1:])
    return ast.Lambda(
        args=ast.arguments(
            posonlyargs=[], args=params, kwonlyargs=[],
            kw_defaults=[], defaults=[],
        ),
        body=body,
    )


# ---- Tree parsing ----


class _Node:
    __slots__ = ("indent", "text", "children")

    def __init__(self, indent, text, children=None):
        self.indent = indent
        self.text = text
        self.children = children or []


def _parse_lines(source):
    """Parse indented source lines into a tree of _Node."""
    root = _Node(-1, None)
    stack = [root]

    for raw in source.splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        node = _Node(indent, text)
        while stack and stack[-1].indent >= indent:
            stack.pop()
        stack[-1].children.append(node)
        stack.append(node)

    return root.children


# ---- AST conversion ----


def _node_to_expr(node):
    """Convert a node to an ast.expr (for block-call arguments)."""
    if node.children:
        args = [_node_to_expr(c) for c in node.children]
        return ast.Call(
            func=ast.Name(id=node.text, ctx=ast.Load()),
            args=args,
            keywords=[],
        )
    return to_expr(node.text)


def _node_to_stmt(node):
    """Convert a single _Node into an ast.stmt."""
    text = node.text

    if text.startswith("fn "):
        rest = text[3:].strip()
        idx = rest.index("[")
        name = rest[:idx].strip()
        params_text = rest[idx + 1:].rstrip("]")
        params = [
            ast.arg(arg=p.strip(), annotation=None)
            for p in params_text.split(",")
            if p.strip()
        ]
        body = _nodes_to_stmts(node.children)
        return ast.FunctionDef(
            name=name,
            args=ast.arguments(
                posonlyargs=[], args=params, kwonlyargs=[],
                kw_defaults=[], defaults=[],
            ),
            body=body,
            decorator_list=[],
        )

    if text.startswith("if "):
        test = to_expr(text[3:])
        body = _nodes_to_stmts(node.children)
        return ast.If(test=test, body=body, orelse=[])

    if text.startswith("while "):
        test = to_expr(text[6:])
        body = _nodes_to_stmts(node.children)
        return ast.While(test=test, body=body, orelse=[])

    if text.startswith("return "):
        return ast.Return(value=to_expr(text[7:]))

    if "=" in text and not text.startswith("["):
        name, val = text.split("=", 1)
        return ast.Assign(
            targets=[ast.Name(id=name.strip(), ctx=ast.Store())],
            value=to_expr(val.strip()),
        )

    # Expression statement
    if node.children or text.startswith("["):
        return ast.Expr(value=_node_to_expr(node))
    if "[" in text:
        return ast.Expr(value=bracket_expr(f"[{text}]"))
    return ast.Expr(value=to_expr(text))


def _nodes_to_stmts(nodes):
    """Convert a list of _Node into a list of ast.stmt, pairing if/while with else."""
    stmts = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if node.text == "else":
            i += 1
            continue
        stmt = _node_to_stmt(node)
        if (
            isinstance(stmt, (ast.If, ast.While))
            and i + 1 < len(nodes)
            and nodes[i + 1].text == "else"
        ):
            stmt.orelse = _nodes_to_stmts(nodes[i + 1].children)
            i += 1
        stmts.append(stmt)
        i += 1
    return stmts


# ---- Public API ----


def compile_pist(source, filename="<pist>"):
    """Compile pist source to a Python code object."""
    nodes = _parse_lines(source)
    stmts = _nodes_to_stmts(nodes)
    mod = ast.Module(body=stmts, type_ignores=[])
    ast.fix_missing_locations(mod)
    return compile(mod, filename, "exec")


# ---- CLI ----


if __name__ == "__main__":
    show_dis = "-d" in sys.argv
    show_ast = "-a" in sys.argv
    filenames = [a for a in sys.argv[1:] if not a.startswith("-")]

    for path in filenames:
        with open(path) as f:
            source = f.read()

        if show_ast:
            nodes = _parse_lines(source)
            stmts = _nodes_to_stmts(nodes)
            mod = ast.Module(body=stmts, type_ignores=[])
            ast.fix_missing_locations(mod)
            print(ast.dump(mod, indent=2))
            continue

        code = compile_pist(source, path)
        ns = {}
        exec(code, ns)

        if show_dis:
            import dis

            dis.dis(code)
