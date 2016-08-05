class Common(object):
	x=0
	def set_variable(self,val):
		self.x = val
		
	def print_variable(self):
		print self.x

class editor(object):
	def __init__(self,common):
		self.common = common
	
	def edit(self,val):
		self.common.set_variable(val)
		
class printer(object):
	def __init__(self,common):
		self.common = common
	
	def print_variable(self):
		self.common.print_variable()
		
if __name__ == '__main__':
	common = Common()
	Editor = editor(common)
	Printer = printer(common)
	
	#Editor.edit(4)
	Printer.print_variable()
	
	Editor.edit(6)
	Printer.print_variable()
