"""
A class hierarchy for a compact and simplified AMR Logical Form representation.

:author: Sergey Goldobin
:date: 06/09/2020

CS 788.01 MS Capstone Project
"""
from typing import *
from bs4 import BeautifulSoup, NavigableString, Tag, Comment


class CommandTemplateError(Exception):
    """
    A simple wrapper for exceptions caused by bad command template formatting.
    """
    pass


# TODO: Move to utilities?
def compose(f: Callable, g: Callable) -> Callable:
    """
    Classic function composition from functional programming.
    compose(f, g) := f.g
    :param f: An arbitrary pure function.
    :param g: An arbitrary pure function.
    :return:
    """
    return lambda x: f(g(x))


class LogicalForm:
    """
    A simplified programmatic representation of the TRIPS Logical Form
    """

    class Component:
        """
        A component of the LF tree structure.
        """

        def __init__(self, comp_id: str, indicator: str = None, comp_type: str = None, word: str = None,
                     resolved: bool = True):
            """
            Create a new LF component.
            :param indicator: The kind of logical form component: SPEECHACT, F, BARE, etc.
            :param comp_type: The specific instance of the indicator, i.e. SA_REQUEST, PERSON, etc.
            :param comp_id: The ID of this component in the form V12345
            :param word: A concrete string representing this component.
            :param resolved: Is the component pending to be replaced by ID?
            """
            # Since Components can be concrete or ambiguous, there must be room to express the ambiguity
            self.comp_id = comp_id  # Must be unique
            self.indicator = [] if not indicator else [indicator]
            self.comp_type = [] if not comp_type else [comp_type]
            self.word = None if not word else [word]
            self.param_mapping = {}  # Storage for parameters which may be bound by some components.
            self._resolved = resolved

            # Optionally, the component may have a set of roles.
            # SPEECHACTs have a CONTENT role, a PUT has AGENT, AFFECTED, and some more.
            self.roles = [{}]  # type: List[Dict[str: List[LogicalForm.Component]]]

        @property
        def bound_params(self) -> Set[str]:
            """
            Get the set of all parameters bound by this Component and all its children.
            :return:
            """
            result = set(self.param_mapping.keys())

            for rg in self.roles:
                for rcs in rg.values():
                    for comp in rcs:
                        result = result.union(comp.bound_params)

            return set(result)

        def _move(self, other):
            """
            Copy the data from another Component into this one. Inspired by C++ move semantics.
            :param other: Component to copy from.
            :return: None
            """
            other = other._root
            self.comp_id = other.comp_id
            self.indicator = list(other.indicator)
            self.comp_type = list(other.comp_type)
            self.word = None if other.word is None else list(other.word)
            self.param_mapping = other.param_mapping
            self._resolved = other._resolved
            self.roles = other.roles

        def __str__(self):
            """
            Get a string representation of the component's base.
            :return: <component [indicator1, ...] [type1, ...] {"" | * | [word1, ...]}>>
            """
            indicators = '*' if not self.indicator else ', '.join(self.indicator)
            comp_types = '*' if not self.comp_type else ', '.join(self.comp_type)
            if self.word is None:
                words = ''
            elif self.word is []:
                words = '*'
            else:
                words = ', '.join(self.word)
            return f'<component {indicators} {comp_types}{"" if len(words) == 0 else f" {words}"}>'

        def __repr__(self):
            return self.__str__()

        def __hash__(self):
            """
            For simplicity, components are issued with unique IDs for hashing.
            :return:
            """
            return hash(self.comp_id)

        def __eq__(self, other):
            return isinstance(other, LogicalForm.Component) and self.comp_id == other.comp_id

        @property
        def resolved(self):
            """
            A component is considered resolved it itself and all descendants are resolved.
            :return:
            """
            result = self._resolved
            for rg in self.roles:
                for rcomps in rg.values():
                    for comp in rcomps:
                        # This being a property propagates changes upwards.
                        result = result and comp.resolved

            return result

        def resolve(self, comps):
            """
            Look through the pieces of the component. Try to match up any unresolved ones with the given dictionary.
            :param comps:
            :return:
            """
            # If this components explicitly expects resolution
            if not self._resolved:
                if self.comp_id not in comps:
                    raise CommandTemplateError(f'Cannot resolve external component ID {self.comp_id}')

                self._move(comps[self.comp_id])  # 'Shift' resolver data into this node
            else:
                # If the component does not expect explicit resolution, its children might
                for rg in self.roles:
                    for cs in rg.values():
                        for c in cs:
                            if not c.resolved:
                                c.resolve(comps)  # TODO Double check that this actually updates the references.

    __component_id = 0

    """
    End of nested class declarations
    """
    def __init__(self, xml_str: str = None, template: Union[str, Tag] = None, require_id: bool = False):
        """
        Given an XML TRIPS parser output or a TRIPS template, process it into a convenient object.
        One of the two strings is required, but not both.
        :param xml_str: The TRIPS parser output.
        :param template: The command template string OR a root BS tag.
        :param require_id: If true, a lack of explicit ID on the component will cause an error. Only affects templates.
        """
        if (xml_str and template) or (not xml_str and not template):
            raise ValueError("Expected either XML string or template, but not both.")

        # Root is the start of the hierarchy of Components
        self._root = None  # type: Union[LogicalForm.Component, None]
        self._require_id = require_id
        self._resolved = False  # Are there any components with a pending from_id?

        if xml_str:
            self._root = LogicalForm._process_xml(xml_str)
            self.from_xml = True
        else:
            self._root = self._process_template(template)
            self.from_xml = False

    def __str__(self):
        return f'LogicalForm {self.my_id}'

    def __repr__(self):
        return self.__str__()

    @property
    def bindings(self) -> Set[str]:
        """
        Get the set of parameters bound by this LogicalForm.
        :return:
        """
        return self._root.bound_params

    """
    Matching
    """
    def match_template(self, lf) -> Tuple[bool, Dict[str, str]]:
        """
        Compare this LogicalForm to another one for structural equality.
        :param lf: Other LogicalForm
        :return: True if the structure and patterns withing the other LogicalForm match this one. False otherwise.
            Additionally, return a dictionary of parameters bound by the compared LF.
        """
        if not isinstance(lf, LogicalForm):
            raise ValueError(f'Expected {LogicalForm} argument, got {type(lf)}.')

        # Recursively walk the structure of the given LF and compare it to own.
        # At any level, there may be multiple branches that are an intermediate match. Recurse down all of them.
        # If a complete match is achieved from multiple recursive calls, pick the first one and report a runtime
        # warning -- the source of the ambiguity is a poorly written template.
        if bool(self._root) != bool(lf._root):
            return False, {}

        if self._root is None and lf._root is None:
            return True, {}

        return LogicalForm._compare_help(self._root, lf._root)

    @staticmethod
    def _compare_help(this, other) -> Tuple[bool, Dict[str, str]]:
        """
        Recursive helper function for LF comparison.
        Parameters will be extracted from 'this' using the mappings of 'other'
        :param this: Compared instance.
        :param other: Instance compared to.
        :return:
        """
        # this and other are expected to be Components at the same level of the tree.
        # Components match if all the following are true:
        # 1) There is overlap between indicator sets
        # 2) There is overlap between type sets
        # 3) There is overlap between word sets
        # 4) There is an exact match within a rolegroup by name
        # 5) There is matching overlap between child components within the matched rolegroup.

        # A role parsed form XML might be a simple string.
        # An equivalent element parsed from a template is a component, since there could be multiple string options
        if isinstance(this, str):
            match = this in other.word
            return match, {p_name: this for p_name in other.param_mapping.keys()}

        # Lists share a common element if their intersection iss a nonempty set.
        lst_common = lambda lst_t: bool(set(lst_t[0]).intersection(set(lst_t[1])))

        # Indicators match if any of them are wildcards (empty lists) or if the intersection of sets is nonempty
        match = not (this.indicator and other.indicator) or lst_common((this.indicator, other.indicator))
        # Same for types
        match = match and (not (this.comp_type and other.comp_type) or lst_common((this.comp_type, other.comp_type)))
        # Same for words
        match = match and (not (this.word and other.word) or lst_common((this.word, other.word)))

        if not match:
            # No surface-level match means no need to recurse further.
            # Also no need to return any parameters from this branch.
            return False, {}

        # TODO: Do we need a warning if there were multiple candidate words? Shouldn't be possible.
        # Map the word value stored in this component to parameter names specified by the template.
        mapped_val = this.word[0] if this.word else None
        param_map = {k: mapped_val for k in other.param_mapping.keys()}

        # Find all the rolegroups that match between this and other.
        check_q = []
        for rg in this.roles:
            for rg_other in other.roles:
                command_roles = set(rg.keys())
                template_roles = set(rg_other.keys())

                # The roles of the template must be a subset of the roles of the command.
                # i.e. If the command has roles A, B, and C, and the template has role B, then the template matches.
                # However, template with B and D is NOT a match to command A, B, C
                if all(r in command_roles for r in template_roles):
                    # The rolegroups match roles
                    check_q.append((rg, rg_other))

        # For each pair of matching rolegroups, recurse on all corresponding components.
        # At least one rolegroup has to match in order for the whole template to match.
        param_set = {}
        one_rg_match = False
        for this_rg, other_rg in check_q:

            # Every role must fully match within a rolegroup
            all_match = True
            rg_set = {}  # set of parameters from this set of roles
            for name in this_rg.keys():
                # Since this RG has been established as a superset of other RG, there may be roles not present
                # in other. That simply means that the role is a match and no parameters are bound.
                if name not in other_rg:
                    continue

                to_match = this_rg[name][0]  # This is the component the template needs to match.
                candidates = other_rg[name]  # This is the candidate components

                # Recurse on all options from the template. At least one must match.
                results = map(lambda x: LogicalForm._compare_help(to_match, x), candidates)
                results = list(filter(lambda x: x[0], results))
                if not results:
                    all_match = False
                    break
                for k, v in results[0][1].items():
                    if k not in rg_set:
                        rg_set[k] = v

            # Stop comparing if we found a matching rolegroup.
            if all_match:
                one_rg_match = True
                param_set = rg_set
                break

        # Not a single rolegroup matched from the template.
        # This component is not a match
        if not one_rg_match:
            return False, {}

        # At least one rolegroup matched.
        # Add the parameters extracted from the matched rolegroup to the set.
        for k, v in param_set.items():
            if k not in param_map:
                param_map[k] = v

        return True, param_map

    """
    ID resolution
    """
    @property
    def my_id(self):
        """
        Get an identifier of this LogicalForm, which corresponds to the ID of the root component.
        :return:
        """
        return self._root.comp_id

    @property
    def resolved(self):
        """
        Are there any elements within the tree that expect an element by ID?
        :return:
        """
        return self._root.resolved

    def resolve(self, comps: Dict[str, Component]) -> NoReturn:
        """
        Marry any unresolved internal components with a given set.
        :param comps: A mapping of component IDs to components.
        :return: None
        """
        if self.resolved:  # No work to do.
            return

        self._root.resolve(comps)

    """
    Pretty Printing functionality
    """
    def pretty_format(self) -> str:
        """
        Construct a "pretty print" string representing the Logical Form.
        It is a mix of XML and AMR notation that keeps it consistent with the XML layout while being more concise.
        Even small trees can get a bit verbose, but this is still a helpful representation.
        :return:
        """
        return LogicalForm.__format_component(self._root, 0, set())

    @staticmethod
    def __format_role(role: Tuple[str, List[Union[Component, str]]], depth: int, seen: Set[Component]) -> str:
        """
        A helper function for pretty_format, mutually recursive with __format_component.
        :param role: The role tuple being formatted.
        :param depth: Nested depth level.
        :param seen: Set of seen Components used to break potential infinite loops.
        :return: String representation of the role.
        """
        role_name, role_comps = role
        result = ('|  ' * depth) + f'<role {role_name}>\n'
        for c in role_comps:
            # Display all of the role's components
            if isinstance(c, str):
                result += ('|  ' * (depth + 1)) + c + '\n'
            else:
                result += LogicalForm.__format_component(c, depth + 1, seen)

        return result

    @staticmethod
    def __format_component(comp: Component, depth: int, seen: Set[Component]) -> str:
        """
        A helper function for pretty_format, mutually recursive with __format_role.
        :param comp: The component being formatted.
        :param depth: Nested depth level.
        :param seen: Set of seen Components used to break potential infinite loops.
        :return: String representation of the component.
        """
        if comp in seen:
            return ''
        seen.add(comp)

        # First, get the base of the component.
        result = ('|  ' * depth) + str(comp) + '\n'
        # Special case for 'closed' components with no child roles.
        if len(comp.roles) == 1 and not comp.roles[0]:
            return result

        for rg in comp.roles:
            # Mark the beginning of a rolegroup
            result += ('|  ' * (depth + 1)) + '<rolegroup>\n'
            # Now show all the roles.
            for rtup in rg.items():
                result += LogicalForm.__format_role(rtup, depth + 2, seen)

            # Mark the end of a rolegroup
            result += ('|  ' * (depth + 1)) + '</rolegroup>\n'

        return result

    """
    String Parsing
    """
    @staticmethod
    def _next_id() -> str:
        """
        Components not explicitly Id'd by a programmer need an ID, and this generates a unique one.
        :return:
        """
        LogicalForm.__component_id -= 1
        return str(LogicalForm.__component_id)

    def _process_template(self, template: Union[str, Tag]) -> Component:
        """
        Convert an XML Command template to logical Form. The command templates contain branching options for component
        structure, which is captured by this function.
        Detailed documentation on the command template format is available here: TODO: Supply link
        :param template: The template encoded string or a root <component> node.
        :return: A root component of the hierarchy.
        """
        if isinstance(template, str):
            bs = BeautifulSoup(template, 'xml')
            command_root = bs.find('component')  # Find the root <component> tag.
        else:
            if template.name != 'component':
                raise CommandTemplateError(f'Unexpected tag {template.name} instead of <component>')
            command_root = template

        if self._require_id:
            if 'id' not in command_root.attrs:
                raise CommandTemplateError('Missing required ID')

        return LogicalForm.__parse_component(command_root)

    @staticmethod
    def __parse_role(root: Tag) -> Tuple[str, List[Component]]:
        """
        Parse a role tag into a mapping of its name to candidate component list.
        :param root: The root <role> node.
        :return: A <role> tuple.
        """
        if root.name != 'role':
            raise CommandTemplateError(f'Unexpected tag {root.name} instead of <role>')

        if 'name' not in root.attrs:
            raise CommandTemplateError('Role missing required "name" attribute')

        role_name = root.attrs['name'].upper()

        # A role may contain one or more expected components, parsed recursively.
        # No components indicates a wildcard accepting anything.
        components = []  # type: List[LogicalForm.Component]
        if not root.children:
            raise CommandTemplateError(f'No components for role {role_name}')

        for child in root.children:
            if (isinstance(child, NavigableString) and child == "\n") or isinstance(child, Comment):
                continue

            # Role children can be plain strings or nested components.
            if isinstance(child, NavigableString) and child != "\n":
                # Interpret plain text role values as closed components with words
                tmp = LogicalForm.Component(LogicalForm._next_id())
                tmp.word = [child.strip(' \n')]
                components.append(tmp)
            else:
                components.append(LogicalForm.__parse_component(child))

        return role_name, components

    @staticmethod
    def __parse_component(root: Tag) -> Component:
        """
        Given a root BS4 tag of a Component, parse it into an object.
        :param root: A Tag representation from BeautifulSoup
        :return: A Component instance.
        """
        # TODO: For extra validation, implement a check for illegal of malformed tags.
        if root.name != 'component':
            raise CommandTemplateError(f'Unexpected tag {root.name} instead of <component>')

        if 'from_id' in root.attrs:
            # The presence of this attribute indicates that the component is defined elsewhere.
            # Store the ID reference to be filled in externally.
            return LogicalForm.Component(root.attrs['from_id'], resolved=False)

        if 'id' in root.attrs:
            # If a programmer supplied an ID, it cannot be a negative number.
            # Everything else is allowed.
            comp_id = root.attrs['id']
            try:
                val = int(comp_id)
                if val < 0:
                    raise CommandTemplateError(f'Negative number {val} is an invalid <component> id.')
            except ValueError:
                pass  # Non-numeric IDs are allowed.
        else:
            # If the programmer did not supply an id, generate a unique one.
            comp_id = LogicalForm._next_id()

        # Generate the baseline component, then fill it in based on supplied attributes and children.
        cmp = LogicalForm.Component(comp_id)

        # This attribute indicates that the words within this component will serve as parameters
        # further in the pipeline. Initialize them in storage.
        if 'map_param' in root.attrs:
            params = map(str.strip, root.attrs['map_param'].split(','))
            for p in params:
                cmp.param_mapping[p] = None  # Values get filled in during template matching.
                # TODO: Could the dictionary be reduced to a set? Actual mapping happens within LogicalForm

        # If any of the following 3 attributes are populated, then those specific values are expected of the template.
        # Otherwise, component lists are left empty to signal a wildcard.
        if 'indicator' in root.attrs:
            cmp.indicator = list(map(compose(str.upper, str.strip), root.attrs['indicator'].split(',')))

        if 'type' in root.attrs:
            cmp.comp_type = list(map(compose(str.upper, str.strip), root.attrs['type'].split(',')))

        if 'word' in root.attrs:
            cmp.word = list(map(compose(str.upper, str.strip), root.attrs['word'].split(',')))
        else:
            # If the word tag was absent, then it's a wildcard.
            cmp.word = []

        # Finally, handle the component's children.
        # The only acceptable children are <role> and <rolegroup> tags.
        # <rolegroup> tags are OR clauses for possible role combinations on the component.
        # <role> tags within a <rolegroup> are AND clauses for the component combination.
        # For syntactic simplicity, a <component> can have only <role>s with no <rolegroup>

        children = list(filter(lambda c: isinstance(c, Tag), root.children))
        # If the component has no children, we are done.
        if not children:
            return cmp

        first_name = children[0].name

        if not all(child.name == first_name for child in children):
            raise CommandTemplateError(f'Role mismatch: Expected either all <rolegroup> or all <role>')

        roleset = 0
        for child in children:
            if child.name == 'rolegroup':
                roles = list(filter(lambda c: isinstance(c, Tag), child.children))
                if len(roles) == 0:
                    raise CommandTemplateError('A <rolegroup> cannot be empty.')

                # Found the next rolegroup. Advance the index and parse all component roles.
                roleset_dict = dict([LogicalForm.__parse_role(r) for r in roles])
                if roleset == len(cmp.roles):
                    cmp.roles.append({})  # Expand role sets storage

                cmp.roles[roleset] = roleset_dict
                roleset += 1
            elif child.name == 'role':
                rkey, rval = LogicalForm.__parse_role(child)
                cmp.roles[roleset][rkey] = rval
            else:
                raise CommandTemplateError(f'Unexpected tag {root.name} instead of <role> or <rolegroup>')

        # Unless there were exceptions, the component is parsed to completion.
        return cmp

    @staticmethod
    def _process_xml(xml_string) -> Component:
        """
        Convert an XML string to a Logical Form.
        :param xml_string: The LF encoded string.
        :return: A root component of the hierarchy.
        """
        bs = BeautifulSoup(xml_string, 'xml')
        components = {}  # type: Dict[str, LogicalForm.Component]

        comp_data = bs.findAll('rdf:Description')

        # First, we need to build up a set of standalone elements with pending ID references.
        # Then, a second pass "marries" the elements into a tree.
        root_id = comp_data[0]['rdf:ID']

        # For each component, extract its indicator, type, and -- if applicable -- word and roles.
        for tags in comp_data:
            component = LogicalForm.Component(tags['rdf:ID'])
            for c in tags.children:
                # Skip meaningless entries.
                if isinstance(c, NavigableString):
                    continue
                if c.name == 'indicator':
                    component.indicator.append(c.text)
                elif c.name == 'type':
                    component.comp_type.append(c.text)
                elif c.name == 'word':
                    if component.word is None:
                        component.word = [c.text]
                    else:
                        component.word.append(c.text)
                elif c.prefix == 'role':
                    # Initialize the list if necessary
                    if c.name not in component.roles[0]:
                        component.roles[0][c.name] = []

                    if 'rdf:resource' in c.attrs:
                        role_comp_id = c['rdf:resource']  # Skip the 'V' prefix if needed
                        # Wrap in a list to allow isinstance() differentiation
                        component.roles[0][c.name].append([role_comp_id])
                    else:
                        # Some roles are basic strings and can be resolved on first pass.
                        component.roles[0][c.name].append(c.text)
            components[component.comp_id] = component

        # All components have been processed. Now, they need to be connected into a tree.
        for comp in components.values():
            for rname, rval in comp.roles[0].items():
                # Only resolve the roles that were left as references.
                resolved_targets = []
                for r_target in rval:
                    if isinstance(r_target, list):
                        resolved_targets.append(components[r_target[0][1:]])
                    else:
                        resolved_targets.append(r_target)
                comp.roles[0][rname] = resolved_targets

        # All components are now connected into a tree structure in memory.
        # Returning a reference to the root component therefore extracts the whole structure.
        return components[root_id]

    """
    Below are modifications made for the Constraint Resolver Independent Study project.
    """

    def get_tree(self) -> Component:
        """
        Grant access to the structure of the logicalForm
        :return:
        """
        return self._root





