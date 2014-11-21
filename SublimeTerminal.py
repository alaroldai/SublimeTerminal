import sublime, sublime_plugin

from math import floor
import os
import sys
import pty
import functools
import select
import fcntl
import termios
import struct

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
		del PTY.instances[self.id]

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
			cpos = sum([len(s) for s in term.screen.display[:y]]) + x
			view.sel().add(sublime.Region(cpos, cpos))
		except KeyError:
			pass

class SublimeTerminalRefreshView(sublime_plugin.TextCommand):
	def run(self, edit):
		term = PTY.instances[self.view.id()]
		self.view.replace(edit, sublime.Region(0, self.view.size()), '\n'.join([l[:-1] for l in term.screen.display]))

class SublimeTerminalNewWindow(sublime_plugin.WindowCommand):
	def run(self):
		view = self.window.new_file()
		view.settings().set('auto_indent', False)
		print(view.settings().get('auto_indent'))
		(wp, hp) = view.viewport_extent()
		(w, h) = (floor(wp / view.em_width()), floor(hp / view.line_height()))

		screen = pyte.Screen(w, h)
		stream = pyte.streams.ByteStream()

		stream.attach(screen)

		(pid, fd) = pty.fork()

		if pid == 0:
			# Child process
			# os.closerange(3, 128)
			os.putenv('TERM', 'ansi')
			winsize = struct.pack("HHHH", int(h), int(w), int(wp), int(hp))
			fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
			termios.tcsetattr(0, termios.TCSANOW, [
				 termios.ICRNL | termios.IXON | termios.IXANY | termios.IMAXBEL | termios.BRKINT
				,termios.OPOST | termios.ONLCR
				,termios.CREAD | termios.CS8 | termios.HUPCL
				,termios.ICANON | termios.ISIG | termios.IEXTEN | termios.ECHOE | termios.ECHOK | termios.ECHOKE | termios.ECHOCTL | termios.ECHO
				,termios.B38400
				,termios.B38400
				,[b'\x04', b'\xff', b'\xff', b'\x7f', b'\x17', b'\x15', b'\x12', b'\x00', b'\x03', b'\x1c', b'\x1a', b'\x19', b'\x11', b'\x13', b'\x16', b'\x0f', b'\x01', b'\x00', b'\x14', b'\x00']])
			os.execlp('/bin/bash', '/bin/bash')

			print("Exec failed!")
			return

		term = PTY(view.id(), stream, screen, fd, pid)

		def loop(t):
			t.read_loop()

		sublime.set_timeout_async(functools.partial(loop, term), 0)