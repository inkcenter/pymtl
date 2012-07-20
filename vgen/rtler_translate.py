"""Tool for translating MTL models to and from HDL source.

This module contains classes which translate between MTL models and various
hardware description languages, such as Verilog.
"""

from rtler_vbase import *
import inspect
import ast

class ToVerilog(object):

  """User visible class for translating MTL models into Verilog source."""

  def __init__(self, model):
    """Construct a Verilog translator from a MTL model.

    Parameters
    ----------
    model: an instantiated MTL model (VerilogModule).
    """
    self.model = model

  def generate(self, o):
    """Generates Verilog source from a MTL model.

    Calls gen_port_decls(), gen_impl_wires(), gen_module_insts(), and gen_ast()
    as necessary.

    Parameters
    ----------
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    target = self.model
    print >> o, 'module %s' % target.class_name
    # Declare Params
    #if self.params: self.gen_param_decls( self.params, o )
    # Declare Ports
    if target.ports: self.gen_port_decls( target.ports, o )
    # Wires & Instantiations
    self.gen_impl_wires( target, o )
    #if self.wires: self.gen_wire_decls( self.wires, o )
    if target.submodules: self.gen_module_insts( target.submodules, o )
    # Logic
    self.gen_ast( target, o )
    # End module
    print >> o, '\nendmodule\n'

  def gen_port_decls(self, ports, o):
    """Generate Verilog source for port declarations.

    Parameters
    ----------
    ports: list of VerilogPort objects.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    print >> o, '('
    for p in ports[:-1]:
      print >> o , '  %s,' % p
    p = ports[-1]
    print >> o, '  %s' % p
    print >> o, ');\n'

  def gen_param_decls(self, params, o):
    """Generate Verilog source for parameter declarations.

    Parameters
    ----------
    params: list of VerilogParam objects.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    print >> o, '#('
    for p in params[:-1]:
      print >> o, '  %s,' % p
    p = params[-1]
    print >> o, '  %s' % p
    print >> o, ')'

  def gen_impl_wires(self, target, o):
    """Creates a list of implied wire objects from connections in the MTL model.

    The MTL modeling framework allows you to make certain connections between
    ports without needing to explicitly declare intermediate wires. In some
    cases Verilog requires these wire declarations to be explicit. This utility
    method attempts to infer these implicit wires, generate VerilogWire objects
    from them, and then add them to the connectivity lists of the necessary
    ports.

    Parameters
    ----------
    target: a VerilogModule instance.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    for submodule in target.submodules:
      for port in submodule.ports:
        if isinstance(port.connections, VerilogWire):
          break
        for c in port.connections:
          if (    c.type != 'wire'
              and c.type != 'constant'
              and c.type != port.type):
            # TODO: figure out a way to get connection submodule name...
            wire_name = '{0}_{1}_TO_{2}_{3}'.format(submodule.name, port.name,
                                                    c.parent.name, c.name)
            wire = VerilogWire(wire_name, port.width)
            c.connections = [wire]
            port.connections = [wire]
            print >> o, '  %s' % wire
    #print

  def gen_wire_decls(self, wires, o):
    """Generate Verilog source for wire declarations.

    Parameters
    ----------
    wires: list of VerilogWire objects.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    for w in wires.values():
      print >> o, '  %s' % w

  def gen_module_insts(self, submodules, o):
    """Generate Verilog source for instantiated submodules.

    Parameters
    ----------
    submodules: list of VerilogModule objects.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    for s in submodules:
      print >> o, ''
      print >> o, '  %s %s' % (s.class_name, s.name)
      # TODO: add params
      print >> o, '  ('
      self.gen_port_insts(s.ports, o)
      print >> o, '  );'

  def gen_port_insts(self, ports, o):
    """Generate Verilog source for submodule port instances.

    Parameters
    ----------
    ports: list of VerilogPort objects.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    # TODO: hacky! fix p.connection
    for p in ports[:-1]:
      name = self.get_parent_connection(p)
      #assert len(p.connections) <= 1
      #name = p.connections[0].name if p.connections else ' '
      print >> o , '    .%s (%s),' % (p.name, name)
    p = ports[-1]
    name = self.get_parent_connection(p)
    #assert len(p.connections) <= 1
    #name = p.connections[0].name if p.connections else ' '
    print >> o, '    .%s (%s)' % (p.name, name)

  def get_parent_connection(self, port):
    """Utility method to find the parent connection in the connection list.

    Currently all VerilogPort objects maintain a list of all other ports they
    are connected to.  If a given VerilogPort is in the middle of a hierarchy,
    ie. when a module A instantiates submodule B, and submodule B instantiates
    another submodule C, the connections list will contain connections to both
    parents and children.  When printing out the instantiation of submodule B,
    we need to know which of the connections leads to the parent so we can
    attach it to module B's port list.  This method attempts to find the parent
    connection by walking though all the port connections and checking them
    one-by-one.

    Parameters
    ----------
    port: a VerilogPort object.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    # TODO: separate connections into inst_cxt and impl_cxn
    if not port.connections:
      return ''
    if len(port.connections) == 1:
      return port.connections[0].name
    for connection in port.connections:
      if port.parent.parent == connection.parent:
        return connection.name

  def gen_ast(self, v, o):
    """Generate Verilog source @combinational annotated python functions.

    Parameters
    ----------
    target: a VerilogModule instance.
    o: the output object to write Verilog source to (ie. sys.stdout).
    """
    #print inspect.getsource( v )  # Doesn't work? Wtf...
    #for x,y in inspect.getmembers(v, inspect.ismethod):
    for x,y in inspect.getmembers(v, inspect.isclass):
      src = inspect.getsource( y )
      tree = ast.parse( src )
      PyToVerilogVisitor( o ).visit(tree)


class FromVerilog(object):

  """User visible class for translating Verilog source into MTL models.

  This class currently only works for creating MTL model interfaces (not
  connectivity or logic). This is useful for building parameterizable Verilog
  generators whose leaf-node logic is all implemented as Verilog source files.
  """

  def __init__(self, filename):
    """Construct a VerilogModule interface object from Verilog source.

    Parameters
    ----------
    filename: the name of the Verilog source file to parse.
    """
    fd = open( filename )
    self.params = []
    self.ports  = []
    self.parse_file( fd )
    # TODO: do the same for params?
    for port in self.ports:
      self.__dict__[port.name] = port

  def __repr__(self):
    return "Module(%s)" % self.name

  def parse_file(self, fd):
    """Utility method for parsing a module in a Verilog source file.

    Parameters
    ----------
    fd: the file descriptor of the Verilog source file which will be parsed.
    """
    start_token = "module"
    end_token   = ");"

    in_module = False
    for line in fd.readlines():
      # Find the beginning of the module definition
      if not in_module and line.startswith( start_token ):
        in_module = True
        self.type = line.split()[1]
        self.name = None
      # Parse parameters
      if in_module and 'parameter' in line:
        self.params += [ VerilogParam( line ) ]
      # Parse inputs
      elif in_module and 'input' in line:
        self.ports += [ VerilogPort( str=line ) ]
      # Parse outputs
      elif in_module and 'output' in line:
        self.ports += [ VerilogPort( str=line ) ]
      # End module definition
      elif in_module and end_token in line:
        in_module = False


class PyToVerilogVisitor(ast.NodeVisitor):
  """Hidden class for translating python AST into Verilog source.

  This class takes the AST tree of a VerilogModule class and looks for any
  functions annotated with the @combinational decorator. These functions are
  translated into Verilog source (in the form of assign statements).

  TODO: change assign statements to "always @ *" blocks?
  """

  opmap = {
      ast.Add      : '+',
      ast.Sub      : '-',
      ast.Mult     : '*',
      ast.Div      : '/',
      ast.Mod      : '%',
      ast.Pow      : '**',
      ast.LShift   : '<<',
      ast.RShift   : '>>>',
      ast.BitOr    : '|',
      ast.BitAnd   : '&',
      ast.BitXor   : '^',
      ast.FloorDiv : '/',
      ast.Invert   : '~',
      ast.Not      : '!',
      ast.UAdd     : '+',
      ast.USub     : '-',
      ast.Eq       : '==',
      ast.Gt       : '>',
      ast.GtE      : '>=',
      ast.Lt       : '<',
      ast.LtE      : '<=',
      ast.NotEq    : '!=',
      ast.And      : '&&',
      ast.Or       : '||',
  }

  def __init__(self, o):
    """Construct a new PyToVerilogVisitor.

    Parameters
    ----------
    o: the output object to write to (ie. sys.stdout).
    """
    self.write_names = False
    self.o = o

  def visit_FunctionDef(self, node):
    """Visit all functions, but only parse those with special decorators."""
    #print node.name, node.decorator_list
    if not node.decorator_list:
      return
    if node.decorator_list[0].id == 'combinational':
      # Visit each line in the function, translate one at a time.
      for x in node.body:
        self.visit(x)

  def visit_BinOp(self, node):
    """Visit all binary operators, convert into Verilog operators.

    Parenthesis are placed around every operator along with its args to ensure
    that the order of operations are preserved.
    """
    print >> self.o, '(',
    self.visit(node.left)
    print PyToVerilogVisitor.opmap[type(node.op)],
    self.visit(node.right)
    print >> self.o, ')',

  def visit_BoolOp(self, node):
    """Visit all boolean operators, TODO: UNIMPLEMENTED."""
    print 'Found BoolOp "%s"' % node.op

  def visit_UnaryOp(self, node):
    """Visit all unary operators, TODO: UNIMPLEMENTED."""
    print 'Found UnaryOp "%s"' % node.op

  #def visit_Num(self, node):
  #  print 'Found Num', node.n

  def visit_AugAssign(self, node):
    """Visit all special assigns, convert <<= ops into assign statements.

    TODO: instead of assign statements, convert into "always @ *" assignments.
    """
    # TODO: this turns all comparisons into assign statements! Fix!
    self.write_names = True
    print >> self.o, '  assign', node.target.id, '=',
    self.visit(node.value)
    print >> self.o, ';'
    self.write_names = False

  #def visit_Compare(self, node):
  #  """Visit all comparisons assigns, convert into Verilog operators."""
  #  print 'Found Comparison "%s"' % node.op

  def visit_Name(self, node):
    """Visit all variables, convert into Verilog variables."""
    if self.write_names: print >> self.o, node.id,


#req_resp_port = FromVerilog("vgen-TestMemReqRespPort.v")
