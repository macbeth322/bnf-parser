import abc
import functools
import logging
import typing

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger('bnf')

RuleName = str
I = typing.TypeVar('I')
O = typing.TypeVar('O')

A0 = typing.TypeVar('A0')
A1 = typing.TypeVar('A1')

def methdispatch(func):
    dispatcher = functools.singledispatch(func)
    def wrapper(*args, **kw):
        return dispatcher.dispatch(args[1].__class__)(*args, **kw)
    wrapper.register = dispatcher.register
    functools.update_wrapper(wrapper, func)
    return wrapper


class Language(object):
    """Collection of rules"""
    def __init__(
        self,
        rules: typing.Dict[RuleName, 'Rule'],
        root_rule: RuleName
    ) -> None:
        self.rules = rules
        self.root_rule = root_rule

    @classmethod
    def create(cls, root_rule: RuleName):
        return cls(dict(), root_rule)

    def add_rule(self, rule: 'Rule') -> 'Language':
        if rule.name in self.rules:
            raise ValueError('Rule with that name is already in this Language')
        self.rules[rule.name] = rule
        return self

    def get_rule(self, rule_name: RuleName) -> 'Rule':
        return self.rules[rule_name]

    def parse(self, text: str) -> 'Node':
        matches = self._parse_all(text)
        node, = matches
        return node

    def _parse_all(self, text: str) -> typing.Iterable['Node']:
        root = self.get_rule(self.root_rule)
        matches = root.match(text, self)
        return (node for _, node in matches)


    def __eq__(self, other: 'Language') -> bool:
        if self.root_rule != other.root_rule:
            LOGGER.info('Langage: root rule is different')
            return False
        elif self.rules.keys() != other.rules.keys():
            LOGGER.info('Language: set of rule names are different')
            return False
        elif self.rules != other.rules:
            LOGGER.info('Language: rules are different')
            return False
        else:
            return True



class Rule(object):
    """Syntax rule

    each transformation in the map must match the format of the syntax
    """
    def __init__(
        self,
        name: RuleName,
        syntax: 'Syntax'
    ) -> None:
        self.name = name
        self.syntax = syntax

    def match(
        self,
        text: str,
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, 'Node']]:
        return self.syntax.match(text, self.name, lang)

    def __eq__(self, other: 'Rule') -> bool:
        if self.name != other.name:
            LOGGER.info('Rule: rule names are different')
            return False
        elif self.syntax != other.syntax:
            LOGGER.info('Rule: syntaxes are different')
            return False
        else:
            return True


class Syntax(object):
    """Collection of Term lists

    a syntax matches if one of its term lists matches the plaintext
    """
    def __init__(self, term_groups: typing.Sequence['TermGroup']) -> None:
        self.term_groups = term_groups

    @classmethod
    def create(cls, *term_groups: 'TermGroup') -> 'Syntax':
        return cls(term_groups)

    def match(
        self,
        text: str,
        rule_name: 'RuleName',
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, 'Node']]:
        for index, term_list in enumerate(self.term_groups):
            for leftover, terms in term_list.match(text, lang):
                node = RuleNode(rule_name, index, terms)
                yield leftover, node


    def __eq__(self, other: 'Syntax') -> bool:
        if self.term_groups != other.term_groups:
            LOGGER.info('Syntax: term groups are different')
            return False
        else:
            return True


class TermGroup(object):
    """Collection of Terms"""
    def __init__(self, terms: typing.Sequence['Term']) -> None:
        self.terms = terms

    @classmethod
    def create(cls, *terms: 'Term') -> 'TermGroup':
        return cls(terms)

    def _match_impl(
        self,
        text: str,
        term_index: int,
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, typing.Sequence['Node']]]:
        term = self.terms[term_index]
        next_term_index = term_index + 1
        is_last_term = next_term_index >= len(self.terms)
        for leftover, match in term.match(text, lang):
            if is_last_term:
                yield leftover, (match,)
            else:
                for final_leftover, child_matches in self._match_impl(
                    leftover,
                    next_term_index,
                    lang
                ):
                    yield final_leftover, (match,) + tuple(child_matches)

    def match(
        self,
        text: str,
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, typing.Sequence['Node']]]:
        return self._match_impl(text, 0, lang)

    def __eq__(self, other: 'TermGroup') -> bool:
        if self.terms != other.terms:
            LOGGER.info('TermGroup: terms are different')
            return False
        else:
            return True


class Term(object, metaclass=abc.ABCMeta):
    """Unit of a syntax"""
    @abc.abstractmethod
    def match(
        self,
        text: str,
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, 'Node']]:
        raise NotImplementedError


class RuleReference(Term):
    """Term that represents a nested rule"""
    def __init__(self, rule_name: RuleName) -> None:
        self.rule_name = rule_name

    def match(
        self,
        text: str,
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, 'Node']]:
        return lang.get_rule(self.rule_name).match(text, lang)

    def __eq__(self, other: 'Term') -> bool:
        if not isinstance(other, RuleReference):
            LOGGER.info('RuleReference: other is not rule reference')
            return False
        elif self.rule_name != other.rule_name:
            LOGGER.info('RuleReference: different rule names')
            return False
        else:
            return True

class Literal(Term):
    """Term that represents a plaintext literal"""
    def __init__(self, text: str) -> None:
        self.text = text

    def match(
        self,
        text: str,
        lang: Language
    ) -> typing.Iterable[typing.Tuple[str, 'Node']]:
        if text.startswith(self.text):
            yield text[len(self.text):], LiteralNode(self.text)

    def __eq__(self, other: 'Term') -> bool:
        if not isinstance(other, Literal):
            LOGGER.info('Literal: other is not a literal')
            return False
        elif self.text != other.text:
            LOGGER.info('Literal: text is different')
            return False
        else:
            return True


class EOFTerm(Term):
    def match(
        self,
        text: str,
        lang: 'Language'
    ) -> typing.Iterable[typing.Tuple[str, 'Node']]:
        if text == '':
            yield text, LiteralNode('')

    def __eq__(self, other: 'Term') -> bool:
        if not isinstance(other, EOFTerm):
            LOGGER.info('EOFTerm: other is not an EOFTerm')
            return False
        else:
            return True


class LanguageTransformation(object):
    def __init__(
        self,
        transformation_rules: typing.Dict[
            RuleName, 'RuleTransformation[typing.Any]'
        ]
    ) -> None:
        self.transformation_rules = transformation_rules

    @classmethod
    def create(cls):
        return cls(dict())

    def add_rule_transformation(
        self,
        rt: 'RuleTransformation'
    ) -> 'LanguageTransformation':
        self.transformation_rules[rt.rule_name] = rt
        return self

    def transform(self, rule_node: 'RuleNode') -> typing.Any:
        return rule_node.transform(self)

    def __ilshift__(
        self,
        info: typing.Tuple[
            RuleName,
            typing.Sequence[typing.Callable[[typing.Any], O]]
        ]
    ) -> 'LanguageTransformation':
        rule_name, transforms = info
        rt = RuleTransformation(
            rule_name,
            SyntaxTransformation(
                tuple(
                    TermGroupTransformation(t) for t in transforms
                )
            )
        )
        self.add_rule_transformation(rt)
        return self


class RuleTransformation(typing.Generic[O]):
    def __init__(
        self,
        rule_name: RuleName,
        tf_syntax: 'SyntaxTransformation[O]'
    ) -> None:
        self.rule_name = rule_name
        self.tf_syntax = tf_syntax

    def transform(
        self,
        rule_node: 'RuleNode',
        lang: 'LanguageTransformation'
    ) -> O:
        return self.tf_syntax.transform(
            rule_node.children,
            rule_node.term_group_id,
            lang
        )


class SyntaxTransformation(typing.Generic[O]):
    def __init__(
        self,
        tf_term_groups: typing.Sequence['TermGroupTransformation[O]']
    ) -> None:
        self.tf_term_groups = tf_term_groups

    @classmethod
    def create(
        cls,
        *tf_term_groups: 'TermGroupTransformation[O]'
    ) -> 'SyntaxTransformation':
        return cls(tf_term_groups)

    def transform(
        self,
        values: typing.Sequence['Node'],
        index: int,
        lang: 'LanguageTransformation'
    ) -> O:
        try:
            return self.tf_term_groups[index].transform(values, lang)
        except IndexError:
            print(index, self.tf_term_groups)
            for v in values:
                print(v)


class TermGroupTransformation(typing.Generic[O]):
    def __init__(
        self,
        accumulator: typing.Callable[[typing.Any], O]
    ) -> None:
        self.accumulator = accumulator

    def transform(
        self,
        values: typing.Sequence['Node'],
        lang: 'LanguageTransformation'
    ) -> O:
        return self.accumulator(
            LazySequenceTransform.create(
                values,
                lang
            )
        )


class Node(object, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def transform(self, lang: 'LanguageTransformation') -> typing.Any:
        raise NotImplementedError


class RuleNode(Node):
    def __init__(
        self,
        matched_rule: RuleName,
        term_group_id: int,
        children: typing.Sequence['Node']
    ) -> None:
        self.matched_rule = matched_rule
        self.term_group_id = term_group_id
        self.children = children

    def __str__(self):
        return ''.join(str(c) for c in self.children)

    def transform(self, lang: 'LanguageTransformation') -> typing.Any:
        return lang.transformation_rules[self.matched_rule].transform(
            self,
            lang
        )


class LiteralNode(Node):
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self):
        return self.value

    def transform(self, lang: 'LanguageTransformation') -> str:
        return self.value

@functools.singledispatch
def _lazy_getitem(_, __):
    raise NotImplementedError

@_lazy_getitem.register(int)
def _lazy_getitem_int(i: int, lazys: 'LazySequenceTransform') -> typing.Any:
    if i not in lazys.cache:
        lazys.cache[i] = lazys.initial_values[i].transform(lazys.lang)
    return lazys.cache[i]

@_lazy_getitem.register(slice)
def _lazy_getitem_slice(
    s: slice,
    lazys: 'LazySequenceTransform'
) -> typing.Sequence:
    return tuple(
        lazys[i]
        for i in range(len(lazys))[s]
    )


class LazySequenceTransform(typing.Sequence):
    def __init__(
        self,
        initial_values: typing.Sequence['Node'],
        lang: 'LanguageTransformation',
        cache: typing.Dict[int, typing.Any]
    ) -> None:
        super().__init__()
        self.initial_values = initial_values
        self.lang = lang
        self.cache = cache

    @classmethod
    def create(
        cls,
        nodes: typing.Sequence['Node'],
        lang: 'LanguageTransformation'
    ) -> 'LazySequenceTransform':
        return cls(nodes, lang, dict())

    @typing.overload
    def __getitem__(self, i: int) -> typing.Any:
        pass
    @typing.overload
    def __getitem__(self, s: slice) -> typing.Sequence: # pylint: disable=function-redefined
        pass
    def __getitem__(self, x): # pylint: disable=function-redefined
        return _lazy_getitem(x, self)

    def __len__(self):
        return len(self.initial_values)

    def __iter__(self):
        return (self[i] for i in range(len(self)))