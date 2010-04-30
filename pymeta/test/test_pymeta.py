from twisted.trial import unittest
from pymeta.runtime import ParseError, OMetaBase, EOFError
from pymeta.boot import BootOMetaGrammar
from pymeta.builder import TreeBuilder, moduleFromGrammar

class HandyWrapper(object):
    """
    Convenient grammar wrapper for parsing strings.
    """
    def __init__(self, klass):
        """
        @param klass: The grammar class to be wrapped.
        """
        self.klass = klass


    def __getattr__(self, name):
        """
        Return a function that will instantiate a grammar and invoke the named
        rule.
        @param: Rule name.
        """
        def doIt(str):
            """
            @param str: The string to be parsed by the wrapped grammar.
            """
            obj = self.klass(str)
            ret = obj.apply(name)
            try:
                extra, err = obj.input.head()
            except EOFError:
                try:
                    return ''.join(ret)
                except TypeError:
                    return ret
            else:
                raise ParseError(err.args[0], err.args[1], "trailing garbage in input: %r" % (extra,))
        return doIt



class OMetaTestCase(unittest.TestCase):
    """
    Tests of OMeta grammar compilation.
    """

    classTested = BootOMetaGrammar

    def compile(self, grammar):
        """
        Produce an object capable of parsing via this grammar.

        @param grammar: A string containing an OMeta grammar.
        """
        g = self.classTested(grammar)
        tree = g.parseGrammar('TestGrammar', TreeBuilder)
        result = moduleFromGrammar(tree, 'TestGrammar', OMetaBase, {})
        return HandyWrapper(result)



    def test_literals(self):
        """
        Input matches can be made on literal characters.
        """
        g = self.compile("digit ::= '1'")
        self.assertEqual(g.digit("1"), "1")
        self.assertRaises(ParseError, g.digit, "4")


    def test_multipleRules(self):
        """
        Grammars with more than one rule work properly.
        """
        g = self.compile("""
                          digit ::= '1'
                          aLetter ::= 'a'
                          """)
        self.assertEqual(g.digit("1"), "1")
        self.assertRaises(ParseError, g.digit, "4")


    def test_escapedLiterals(self):
        """
        Input matches can be made on escaped literal characters.
        """
        g = self.compile(r"newline ::= '\n'")
        self.assertEqual(g.newline("\n"), "\n")


    def test_integers(self):
        """
        Input matches can be made on literal integers.
        """
        g = self.compile("stuff ::= 17 0x1F -2 0177")
        self.assertEqual(g.stuff([17, 0x1f, -2, 0177]), 0177)
        self.assertRaises(ParseError, g.stuff, [1, 2, 3])


    def test_star(self):
        """
        Input matches can be made on zero or more repetitions of a pattern.
        """
        g = self.compile("xs ::= 'x'*")
        self.assertEqual(g.xs(""), "")
        self.assertEqual(g.xs("x"), "x")
        self.assertEqual(g.xs("xxxx"), "xxxx")
        self.assertRaises(ParseError, g.xs, "xy")


    def test_plus(self):
        """
        Input matches can be made on one or more repetitions of a pattern.
        """
        g = self.compile("xs ::= 'x'+")
        self.assertEqual(g.xs("x"), "x")
        self.assertEqual(g.xs("xxxx"), "xxxx")
        self.assertRaises(ParseError, g.xs, "xy")
        self.assertRaises(ParseError, g.xs, "")


    def test_sequencing(self):
        """
        Input matches can be made on a sequence of patterns.
        """
        g = self.compile("twelve ::= '1' '2'")
        self.assertEqual(g.twelve("12"), "2");
        self.assertRaises(ParseError, g.twelve, "1")


    def test_alternatives(self):
        """
        Input matches can be made on one of a set of alternatives.
        """
        g = self.compile("digit ::= '0' | '1' | '2'")
        self.assertEqual(g.digit("0"), "0")
        self.assertEqual(g.digit("1"), "1")
        self.assertEqual(g.digit("2"), "2")
        self.assertRaises(ParseError, g.digit, "3")


    def test_optional(self):
        """
        Subpatterns can be made optional.
        """
        g = self.compile("foo ::= 'x' 'y'? 'z'")
        self.assertEqual(g.foo("xyz"), 'z')
        self.assertEqual(g.foo("xz"), 'z')


    def test_apply(self):
        """
        Other productions can be invoked from within a production.
        """
        g = self.compile("""
              digit ::= '0' | '1'
              bits ::= <digit>+
            """)
        self.assertEqual(g.bits('0110110'), '0110110')


    def test_negate(self):
        """
        Input can be matched based on its failure to match a pattern.
        """
        g = self.compile("foo ::= ~'0' <anything>")
        self.assertEqual(g.foo("1"), "1")
        self.assertRaises(ParseError, g.foo, "0")


    def test_ruleValue(self):
        """
        Productions can specify a Python expression that provides the result
        of the parse.
        """
        g = self.compile("foo ::= '1' => 7")
        self.assertEqual(g.foo('1'), 7)


    def test_ruleValueEscapeQuotes(self):
        """
        Escaped quotes are handled properly in Python expressions.
        """
        g = self.compile(r"""escapedChar ::= '\'' => '\\\''""")
        self.assertEqual(g.escapedChar("'"), "\\'")

        
    def test_ruleValueEscapeSlashes(self):
        """
        Escaped slashes are handled properly in Python expressions.
        """
        g = self.compile(r"""escapedChar ::= '\\' => '\\'""")
        self.assertEqual(g.escapedChar("\\"), "\\")

        
        
    def test_lookahead(self):
        """
        Doubled negation does lookahead.
        """
        g = self.compile("""
                         foo ::= ~~(:x) <bar x>
                         bar :x ::= :a :b ?(x == a == b) => x
                         """)
        self.assertEqual(g.foo("11"), '1')
        self.assertEqual(g.foo("22"), '2')


    def test_binding(self):
        """
        The result of a parsing expression can be bound to a name.
        """
        g = self.compile("foo ::= '1':x => int(x) * 2")
        self.assertEqual(g.foo("1"), 2)


    def test_bindingAccess(self):
        """
        Bound names in a rule can be accessed on the grammar's "locals" dict.
        """
        gg = self.classTested("stuff ::= '1':a ('2':b | '3':c)")
        t = gg.parseGrammar('TestGrammar', TreeBuilder)
        G = moduleFromGrammar(t, 'TestGrammar', OMetaBase, {})
        g = G("12")
        self.assertEqual(g.apply("stuff"), '2')
        self.assertEqual(g.locals['stuff']['a'], '1')
        self.assertEqual(g.locals['stuff']['b'], '2')
        g = G("13")
        self.assertEqual(g.apply("stuff"), '3')
        self.assertEqual(g.locals['stuff']['a'], '1')
        self.assertEqual(g.locals['stuff']['c'], '3')


    def test_predicate(self):
        """
        Python expressions can be used to determine the success or failure of a
        parse.
        """
        g = self.compile("""
              digit ::= '0' | '1'
              double_bits ::= <digit>:a <digit>:b ?(a == b) => int(b)
           """)
        self.assertEqual(g.double_bits("00"), 0)
        self.assertEqual(g.double_bits("11"), 1)
        self.assertRaises(ParseError, g.double_bits, "10")
        self.assertRaises(ParseError, g.double_bits, "01")


    def test_parens(self):
        """
        Parens can be used to group subpatterns.
        """
        g = self.compile("foo ::= 'a' ('b' | 'c')")
        self.assertEqual(g.foo("ab"), "b")
        self.assertEqual(g.foo("ac"), "c")


    def test_action(self):
        """
        Python expressions can be run as actions with no effect on the result
        of the parse.
        """
        g = self.compile("""foo ::= ('1'*:ones !(False) !(ones.insert(0, '0')) => ''.join(ones))""")
        self.assertEqual(g.foo("111"), "0111")


    def test_bindNameOnly(self):
        """
        A pattern consisting of only a bind name matches a single element and
        binds it to that name.
        """
        g = self.compile("foo ::= '1' :x '2' => x")
        self.assertEqual(g.foo("132"), "3")


    def test_args(self):
        """
        Productions can take arguments.
        """
        g = self.compile("""
              digit ::= ('0' | '1' | '2'):d => int(d)
              foo :x ::= (?(x > 1) '9' | ?(x <= 1) '8'):d => int(d)
              baz ::= <digit>:a <foo a>:b => [a, b]
            """)
        self.assertEqual(g.baz("18"), [1, 8])
        self.assertEqual(g.baz("08"), [0, 8])
        self.assertEqual(g.baz("29"), [2, 9])
        self.assertRaises(ParseError, g.foo, "28")


    def test_patternMatch(self):
        """
        Productions can pattern-match on arguments.
        Also, multiple definitions of a rule can be done in sequence.
        """
        g = self.compile("""
              fact 0                       => 1
              fact :n ::= <fact (n - 1)>:m => n * m
           """)
        self.assertEqual(g.fact([3]), 6)


    def test_listpattern(self):
        """
        Brackets can be used to match contents of lists.
        """
        g = self.compile("""
             digit  ::= :x ?(x.isdigit())          => int(x)
             interp ::= [<digit>:x '+' <digit>:y] => x + y
           """)
        self.assertEqual(g.interp([['3', '+', '5']]), 8)

    def test_listpatternresult(self):
        """
        The result of a list pattern is the entire list.
        """
        g = self.compile("""
             digit  ::= :x ?(x.isdigit())          => int(x)
             interp ::= [<digit>:x '+' <digit>:y]:z => (z, x + y)
        """)
        e = ['3', '+', '5']
        self.assertEqual(g.interp([e]), (e, 8))

    def test_recursion(self):
        """
        Rules can call themselves.
        """
        g = self.compile("""
             interp ::= (['+' <interp>:x <interp>:y] => x + y
                       | ['*' <interp>:x <interp>:y] => x * y
                       | :x ?(isinstance(x, str) and x.isdigit()) => int(x))
             """)
        self.assertEqual(g.interp([['+', '3', ['*', '5', '2']]]), 13)


    def test_leftrecursion(self):
         """
         Left-recursion is detected and compiled appropriately.
         """
         g = self.compile("""
               num ::= (<num>:n <digit>:d   => n * 10 + d
                      | <digit>)
               digit ::= :x ?(x.isdigit()) => int(x)
              """)
         self.assertEqual(g.num("3"), 3)
         self.assertEqual(g.num("32767"), 32767)


    def test_characterVsSequence(self):
        """
        Characters (in single-quotes) are not regarded as sequences.
        """
        g = self.compile("""
        interp ::= ([<interp>:x '+' <interp>:y] => x + y
                  | [<interp>:x '*' <interp>:y] => x * y
                  | :x ?(isinstance(x, basestring) and x.isdigit()) => int(x))
        """)
        self.assertEqual(g.interp([['3', '+', ['5', '*', '2']]]), 13)
        self.assertEqual(g.interp([[u'3', u'+', [u'5', u'*', u'2']]]), 13)


    def test_string(self):
        """
        Strings in double quotes match string objects.
        """
        g = self.compile("""
             interp ::= ["Foo" 1 2] => 3
           """)
        self.assertEqual(g.interp([["Foo", 1, 2]]), 3)

    def test_argEscape(self):
        """
        Regression test for bug #239344.
        """
        g = self.compile("""
            memo_arg :arg ::= <anything> ?(False)
            trick ::= <letter> <memo_arg 'c'>
            broken ::= <trick> | <anything>*
        """)
        self.assertEqual(g.broken('ab'), 'ab')


    def test_comments(self):
        """
        Comments in grammars are accepted and ignored.
        """
        g = self.compile("""
        #comment here
        digit ::= ( '0' #second comment
                  | '1') #another one
        bits ::= <digit>+   #last one
        """)
        self.assertEqual(g.bits('0110110'), '0110110')



class PyExtractorTest(unittest.TestCase):
    """
    Tests for finding Python expressions in OMeta grammars.
    """

    def findInGrammar(self, expr):
        """
        L{OMeta.pythonExpr()} can extract a single Python expression from a
        string, ignoring the text following it.
        """
        o = OMetaBase(expr + "\nbaz ::= ...\n")
        self.assertEqual(o.pythonExpr()[0][0], expr)


    def test_expressions(self):
        """
        L{OMeta.pythonExpr()} can recognize various paired delimiters properly
        and include newlines in expressions where appropriate.
        """
        self.findInGrammar("x")
        self.findInGrammar("(x + 1)")
        self.findInGrammar("{x: (y)}")
        self.findInGrammar("x, '('")
        self.findInGrammar('x, "("')
        self.findInGrammar('x, """("""')
        self.findInGrammar('(x +\n 1)')
        self.findInGrammar('[x, "]",\n 1]')
        self.findInGrammar('{x: "]",\ny: "["}')

        o = OMetaBase("foo(x[1]])\nbaz ::= ...\n")
        self.assertRaises(ParseError, o.pythonExpr)
        o = OMetaBase("foo(x[1]\nbaz ::= ...\n")
        self.assertRaises(ParseError, o.pythonExpr)


class MakeGrammarTest(unittest.TestCase):
    """
    Test the definition of grammars via the 'makeGrammar' method.
    """


    def test_makeGrammar(self):
        #imported here to prevent OMetaGrammar from being constructed before
        #tests are run
        from pymeta.grammar import OMeta
        results = []
        grammar = """
        digit ::= :x ?('0' <= x <= '9') => int(x)
        num ::= (<num>:n <digit>:d !(results.append(True)) => n * 10 + d
               | <digit>)
        """
        TestGrammar = OMeta.makeGrammar(grammar, {'results':results})
        g = TestGrammar("314159")
        self.assertEqual(g.apply("num"), 314159)
        self.assertNotEqual(len(results), 0)


    def test_brokenGrammar(self):
        from pymeta.grammar import OMeta
        grammar = """
        andHandler ::= <handler>:h1 'and' <handler>:h2 => And(h1, h2)
        """
        e = self.assertRaises(ParseError, OMeta.makeGrammar, grammar, {})
        self.assertEquals(e.position, 37)
        self.assertEquals(e.error, [("leftover", grammar[37:])])


    def test_subclassing(self):
        """
        A subclass of an OMeta subclass should be able to call rules on its
        parent.
        """
        from pymeta.grammar import OMeta

        grammar1 = """
        dig ::= :x ?('0' <= x <= '9') => int(x)
        """
        TestGrammar1 = OMeta.makeGrammar(grammar1, {})

        grammar2 = """
        num ::= (<num>:n <dig>:d => n * 10 + d
                | <dig>)
        """
        TestGrammar2 = TestGrammar1.makeGrammar(grammar2, {})
        g = TestGrammar2("314159")
        self.assertEqual(g.apply("num"), 314159)


    def test_super(self):
        """
        Rules can call the implementation in a superclass.
        """
        from pymeta.grammar import OMeta
        grammar1 = "expr ::= <letter>"
        TestGrammar1 = OMeta.makeGrammar(grammar1, {})
        grammar2 = "expr ::= <super> | <digit>"
        TestGrammar2 = TestGrammar1.makeGrammar(grammar2, {})
        self.assertEqual(TestGrammar2("x").apply("expr"), "x")
        self.assertEqual(TestGrammar2("3").apply("expr"), "3")

class SelfHostingTest(OMetaTestCase):
    """
    Tests for the OMeta grammar parser defined with OMeta.
    """
    classTested = None


    def setUp(self):
        """
        Run the OMeta tests with the self-hosted grammar instead of the boot
        one.
        """
        #imported here to prevent OMetaGrammar from being constructed before
        #tests are run
        if self.classTested is None:
            from pymeta.grammar import OMetaGrammar
            self.classTested = OMetaGrammar



class NullOptimizerTest(OMetaTestCase):
    """
    Tests of OMeta grammar compilation via the null optimizer.
    """

    def compile(self, grammar):
        """
        Produce an object capable of parsing via this grammar.

        @param grammar: A string containing an OMeta grammar.
        """
        from pymeta.grammar import OMetaGrammar, NullOptimizer
        g = OMetaGrammar(grammar)
        tree  = g.parseGrammar('TestGrammar', TreeBuilder)
        opt = NullOptimizer([tree])
        opt.builder = TreeBuilder("TestGrammar", opt)
        tree = opt.apply("grammar")
        grammarClass = moduleFromGrammar(tree, 'TestGrammar', OMetaBase, {})
        return HandyWrapper(grammarClass)

class ErrorReportingTests(unittest.TestCase):


    def compile(self, grammar):
        """
        Produce an object capable of parsing via this grammar.

        @param grammar: A string containing an OMeta grammar.
        """
        g = BootOMetaGrammar(grammar)
        tree = g.parseGrammar('TestGrammar', TreeBuilder)
        result = moduleFromGrammar(tree, 'TestGrammar', OMetaBase, {})
        return HandyWrapper(result)


    def test_rawReporting(self):
        g = self.compile("""

        start ::= ( (<person> <feeling> <target>)
                  | (<adjective> <animal> <feeling> <token "some"> <target>))
        adjective ::= <token "crazy"> | <token "clever"> | <token "awesome">
        feeling ::= <token "likes"> | <token "loves"> | <token "hates">
        animal ::= <token "monkey"> | <token "horse"> | <token "unicorn">
        person ::= <token "crazy horse"> | <token "hacker">
        target ::= (<token "bananas"> | <token "robots"> | <token "americans">
                   | <token "bacon">)
        """)

        #some warmup
        g.start("clever monkey hates some robots")
        g.start("awesome unicorn loves some bacon")
        g.start("crazy horse hates americans")
        g.start("hacker likes robots")

        e = self.assertRaises(ParseError, g.start,
                              "clever hacker likes bacon")
        self.assertEqual(e.position, 8)
        self.assertEqual(e.error, [('expected', "token", "'horse'")])

        e = self.assertRaises(ParseError, g.start,
                              "crazy horse likes some grass")

        #matching "some" means second branch of 'start' is taken
        self.assertEqual(e.position, 23)
        self.assertEqual(e.error, [('expected', "token", "'bananas'"),
                                   ('expected', "token", "'robots'"),
                                   ('expected', "token", "'americans'"),
                                   ('expected', 'token', "'bacon'")])

        e = self.assertRaises(ParseError, g.start,
                              "crazy horse likes mountains")

        #no "some" means first branch of 'start' is taken...
        #but second is also viable
        self.assertEqual(e.position, 18)
        self.assertEqual(e.error, [('expected', "token", "'bananas'"),
                                   ('expected', "token", "'robots'"),
                                   ('expected', "token", "'americans'"),
                                   ('expected', 'token', "'bacon'"),
                                   ('expected', "token", "'some'")])
