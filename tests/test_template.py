import unittest
from types import SimpleNamespace

from b109tasks.template import Template, TemplateSyntaxError, UndefinedError, render, resolve_path


class TemplateTest(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(render("no tags here"), "no tags here")

    def test_variables_and_paths(self):
        ctx = {"user": {"name": "ada", "team": SimpleNamespace(name="core")}}
        self.assertEqual(render("{{ user.name }}/{{ user.team.name }}", ctx), "ada/core")

    def test_filters(self):
        ctx = {"name": "  grace hopper ", "tags": ["a", "b"]}
        self.assertEqual(render("{{ name|trim|title }}", ctx), "Grace Hopper")
        self.assertEqual(render("{{ name|trim|upper }}", ctx), "GRACE HOPPER")
        self.assertEqual(render('{{ tags|join:", " }} ({{ tags|length }})', ctx), "a, b (2)")

    def test_default_filter(self):
        self.assertEqual(render('{{ missing|default:"n/a" }}', {}), "n/a")
        self.assertEqual(render('{{ empty|default:"n/a" }}', {"empty": ""}), "n/a")
        self.assertEqual(render('{{ x|default:"n/a" }}', {"x": 0}), "0")

    def test_undefined_raises(self):
        with self.assertRaises(UndefinedError):
            render("{{ nope }}", {})

    def test_autoescape(self):
        ctx = {"v": "<b>&</b>"}
        self.assertEqual(render("{{ v }}", ctx), "&lt;b&gt;&amp;&lt;/b&gt;")
        self.assertEqual(render("{{ v }}", ctx, autoescape=False), "<b>&</b>")

    def test_if_else(self):
        tpl = Template("{% if admin %}admin{% else %}user{% endif %}")
        self.assertEqual(tpl.render({"admin": True}), "admin")
        self.assertEqual(tpl.render({"admin": False}), "user")
        self.assertEqual(tpl.render({}), "user")

    def test_if_not_and_nesting(self):
        src = "{% if a %}A{% if not b %}-notb{% endif %}{% endif %}."
        self.assertEqual(render(src, {"a": 1, "b": 0}), "A-notb.")
        self.assertEqual(render(src, {"a": 1, "b": 1}), "A.")
        self.assertEqual(render(src, {"a": 0}), ".")

    def test_syntax_errors(self):
        for src in ["{% if x %}", "{% endif %}", "{% else %}", "{% loop %}", "{{ a b }}",
                    "{{ x|nosuch }}", "{{ x|default:n/a }}"]:
            with self.subTest(src=src), self.assertRaises(TemplateSyntaxError):
                render(src, {"x": 1})


class ForLoopTest(unittest.TestCase):
    def test_loop(self):
        ctx = {"users": [{"name": "ada", "admin": True}, {"name": "bob", "admin": False}]}
        src = ("{% for u in users %}{{ loop.index }}.{{ u.name }}"
               "{% if u.admin %}*{% endif %}{% if not loop.last %}, {% endif %}{% endfor %}")
        self.assertEqual(render(src, ctx), "1.ada*, 2.bob")

    def test_nested_and_empty(self):
        ctx = {"rows": [[1, 2], [], [3]]}
        self.assertEqual(render("{% for r in rows %}[{% for c in r %}{{ c }}{% endfor %}]{% endfor %}", ctx),
                         "[12][][3]")

    def test_scope(self):
        src = "{{ x }}{% for x in xs %}{{ x }}{% endfor %}{{ x }}"
        self.assertEqual(render(src, {"x": "o", "xs": ["a", "b"]}), "oabo")
        with self.assertRaises(UndefinedError):
            render("{% for y in ys %}{% endfor %}{{ y }}", {"ys": [1]})
        with self.assertRaises(UndefinedError):
            render("{% for y in missing %}{% endfor %}", {})

    def test_loop_syntax_errors(self):
        for src in ["{% for x in %}{% endfor %}", "{% for x in xs %}", "{% endfor %}",
                    "{% if a %}{% endfor %}", "{% for x in xs %}{% else %}{% endfor %}"]:
            with self.subTest(src=src), self.assertRaises(TemplateSyntaxError):
                Template(src)


class ResolvePathTest(unittest.TestCase):
    def test_lookup(self):
        ctx = {"a": {"b": SimpleNamespace(c=3)}}
        self.assertEqual(resolve_path(ctx, "a.b.c"), 3)
        with self.assertRaises(UndefinedError):
            resolve_path(ctx, "zz")


if __name__ == "__main__":
    unittest.main()
