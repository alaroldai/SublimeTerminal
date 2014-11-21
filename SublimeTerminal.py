import sublime, sublime_plugin

from math import floor
import os
import sys
import pty
import functools
import select

cmd_folder = os.path.realpath(os.path.dirname(os.path.abspath( __file__ )))
if cmd_folder not in sys.path:
    sys.path.append(cmd_folder)

import pyte

class PTY:
	instances = {}
	def __init__(self, viewid, stream, screen, fd, client_pid):
		self.stream = stream
		self.screen = screen
		self.id = viewid
		self.fd = fd
		self.client_pid = client_pid

		PTY.instances[viewid] = self

	def update(self):
		print('update called')
		all_windows = sublime.windows()
		views = []
		[views.append(v) for w in all_windows for v in w.views() if v.id() == self.id]

		if views:
			views[0].run_command('sublime_terminal_refresh_view')
			return True
		else:
			return False

	def reader(self):
		data = os.read(self.fd, 1000)
		if not data:
			return False
		self.stream.feed(data)
		return self.update()

	def read_loop(self):
		while True:
			(r, w, x) = select.select([self.fd], [], [], 10)
			if not r:
				break
			if not self.reader():
				break
		print('closing read loop, sending kill signal (HUP) to pid {}'.format(self.client_pid))

		os.close(self.fd)
		os.kill(self.client_pid, 1)

class PTYInputEventListener(sublime_plugin.EventListener):
	def on_modified(self, view):
		try:
			term = PTY.instances[view.id()]
			fd = term.fd
			cmd = view.command_history(0)
			chars = ''
			if cmd[0] == 'insert':

				
				chars = bytes(view.command_history(0)[1]['characters'], 'UTF-8')
			elif cmd[0] == 'left_delete':
				chars = bytes(pyte.control.BS, 'UTF-8')
			if chars:
				os.write(fd, chars)
			view.sel().clear()
			x, y = term.screen.cursor.x, term.screen.cursor.y
			cpos = sum([len(s) - 1 for s in term.screen.display[:y]]) + x
			view.sel().add(sublime.Region(cpos, cpos))
		except KeyError:
			pass

class SublimeTerminalRefreshView(sublime_plugin.TextCommand):
	def run(self, edit):
		term = PTY.instances[self.view.id()]
		self.view.replace(edit, sublime.Region(0, self.view.size()), ''.join([l[:-1] for l in term.screen.display]))

class SublimeTerminalNewWindow(sublime_plugin.WindowCommand):
	def run(self):
		view = self.window.new_file()
		view.settings().set('auto_indent', False)
		print(view.settings().get('auto_indent'))
		(w, h) = view.viewport_extent()
		(w, h) = (floor(w / view.em_width()), floor(h / view.line_height()))

		screen = pyte.Screen(w, h)
		stream = pyte.streams.ByteStream()

		stream.attach(screen)

		(pid, fd) = pty.fork()

		if pid == 0:
			# Child process
			# os.closerange(3, 128)
			os.execlp('/bin/bash', '/bin/bash')

			print("Exec failed!")
			return

		term = PTY(view.id(), stream, screen, fd, pid)

		def loop(t):
			t.read_loop()

		sublime.set_timeout_async(functools.partial(loop, term), 0)