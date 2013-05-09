import gtk, gobject, pygtk
pygtk.require('2.0')
gobject.threads_init()

import json
import math
import pango
import signal
import socket
import sys
import threading
import time
import traceback
import urllib
import urllib2
import urllib3

PATH = '/render/?'
DEFAULT_FG = '#f0f0f0'
DEFAULT_BG = '#333333'
PADDING = 1

connpool = urllib3.PoolManager(10, timeout=10, maxsize=3, block=True)

CONFIG = {}

class Graph(gtk.Image):
	width = 300
	height = 200

	_thread = None
	_thread_started = False
	_stop = False
	pixbuf = None
	last_update = 0

	def __init__(self, params):
		super(Graph, self).__init__()
		self.params = params
		self._thread = threading.Thread(target=self._reload)

	def stop(self, widget):
		self._stop = True

	def _get_url(self):
		qs = [
			'_salt=%d' % time.time(),
			'bgcolor=%s' % urllib.quote_plus(CONFIG.get('bgcolor', DEFAULT_BG)),
			'height=%d' % self.height,
			'width=%d' % self.width,
		]

		for k, v in self.params.iteritems():
			if k == 'targets':
				for target in v:
					qs.append('target=%s' % urllib.quote_plus(target))
			else:
				qs.append('%s=%s' % (k, urllib.quote_plus(str(v))))

		return CONFIG['graphiteWebRoot'] + PATH + '&'.join(qs)

	def _draw(self, img_data=None, saturated=False):
		if img_data:
			self.saturated = saturated
			pixbuf_loader = gtk.gdk.PixbufLoader()
			pixbuf_loader.write(img_data)
			self.pixbuf = pixbuf_loader.get_pixbuf()
			pixbuf_loader.close()

		b = self.pixbuf.scale_simple(self.width, self.height, gtk.gdk.INTERP_BILINEAR)

		self.set_from_pixbuf(b)
		self.queue_draw()

	def _draw_outdated(self):
		if not self.pixbuf:
			return

		if not self.saturated:
			self.saturated = True
			self.pixbuf.saturate_and_pixelate(self.pixbuf, 0, False)

		self._draw()

	def _reload(self):
		while True:
			try:
				r = connpool.request('GET', self._get_url(), retries=1)
				gobject.idle_add(self._draw, r.data)
			except:
				gobject.idle_add(self._draw_outdated)
				traceback.print_exc()

			for _ in range(CONFIG.get('graphUpdateInterval', 10)):
				if self._stop:
					return
				time.sleep(1)

	def scale_from_window(self, window, rect, rows, cols):
		if not self._thread_started:
			self._thread_started = True
			self._thread.start()

		width = (rect.width / cols) - 5
		height = (rect.height / rows) - 5

		if width != self.width or height != self.height:
			self.width = Graph.width = width
			self.height = Graph.height = height
			if not self.pixbuf:
				self._draw()

class StatsPi(object):
	# If the config update thread should stop running
	_stop = False

	# The graphs that we're currently tracking
	graphs = []

	def __init__(self):
		self.win = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.win.connect('destroy', self.destroy)

		self.win.set_title('StatsPi')

		if not DEBUG:
			self.win.fullscreen()

		self.win.show_all()

		if not DEBUG:
			pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
			color = gtk.gdk.Color()
			cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
			self.win.window.set_cursor(cursor)

		threading.Thread(target=self._update_graphs).start()

	def _reset(self):
		color = gtk.gdk.color_parse(CONFIG.get('bgcolor', DEFAULT_BG))
		self.win.modify_bg(gtk.STATE_NORMAL, color)

		for c in self.win.get_children():
			# All of the children of table are cleared and stopped from table's "destroy" event
			self.win.remove(c)

	def _update_graphs(self):
		hostname = socket.gethostname().lower()

		while True:
			self._update_config()

			hosts = [h.lower() for h in CONFIG['hosts']]

			if hostname not in hosts:
				self.graphs = []
				gobject.idle_add(self._display_host_error, hostname)
			else:
				graphs = self._get_host_graphs(hostname)
				if self._should_update(graphs):
					self.graphs = graphs
					gobject.idle_add(self._display_graphs, graphs)

			for _ in range(CONFIG.get('configUpdateInterval', 60)):
				if self._stop:
					return
				time.sleep(1)

	def _should_update(self, graphs):
		if len(self.graphs) != len(graphs):
			return True

		# Only clear everything if our graphs have changed
		for s, g in zip(self.graphs, graphs):
			if cmp(s, g) != 0:
				return True

		return False

	def _display_host_error(self, hostname):
		self._reset()

		buff = gtk.TextBuffer()
		buff.set_text('Error\nHost "%s" not found in config' % hostname)

		msg = gtk.TextView(buff)
		msg.modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse('#333'))
		msg.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('red'))
		msg.modify_font(pango.FontDescription("bold 18"))
		msg.set_justification(gtk.JUSTIFY_CENTER)

		fixed = gtk.Alignment(.5, .5, .1, .1)
		fixed.add(msg)
		fixed.show_all()

		self.win.add(fixed)

	def _update_config(self):
		while True:
			try:
				# Avoid a race condition by finishing the request before updating the config
				cfg = json.load(urllib2.urlopen(CONFIG_URL, timeout=5))

				CONFIG.clear()
				CONFIG.update(cfg)

				return
			except:
				traceback.print_exc()
				time.sleep(5)

	def _display_graphs(self, graphs):
		self._reset()

		dim = 0
		graphs_len = len(graphs)
		while math.pow(dim, 2) < graphs_len:
			dim += 1

		cols = rows = dim
		if (cols * rows) - cols >= graphs_len:
			rows -= 1

		self.table = gtk.Table(rows, cols, True)
		self.table.set_resize_mode(gtk.RESIZE_QUEUE)

		row = 0
		col = 0
		for graph in graphs:
			g = Graph(graph)
			self.table.attach(g, row, row + 1, col, col + 1, gtk.FILL|gtk.EXPAND, gtk.FILL|gtk.EXPAND)
			self.win.connect('size-allocate', g.scale_from_window, rows, cols)
			self.table.connect('destroy', g.stop)
			row += 1
			if row % cols == 0:
				col += 1
				row = 0

		self.win.add(self.table)
		self.table.show_all()
		self.win.show_all()

	def _get_host_graphs(self, hostname):
		""" Loads the graph config and decides which graphs are meant for us.
		"""

		def prepare_graph(suite, graph):
			g = CONFIG['params'].copy()
			g.update(graph)
			g['title'] = '%s: %s' % (suite, g.get('title', '(no title)'))
			return g

		host_graphs = []
		for suite, graphs in CONFIG['graphs'].iteritems():
			for graph in graphs:
				host_graphs.append(prepare_graph(suite, graph))

		# Graphs should be divided equally amongst all hosts
		hosts = CONFIG['hosts']
		host_len = len(hosts)
		per_host = int(math.ceil(len(host_graphs) / float(host_len)))

		# The total number of graphs that will be displayed with this split
		displayed = per_host * host_len

		# Where the graphs for this host start
		start = hosts.index(hostname) * per_host

		# If there are extra graphs that don't divide equally, they go to the last host
		if displayed < len(host_graphs) and hosts.index(hostname) == len(hosts)-1:
			host_graphs = host_graphs[start:]
		else:
			host_graphs = host_graphs[start:start+per_host]

		return host_graphs

	def destroy(self, widget=None, data=None):
		self._stop = True
		gtk.main_quit()

	def main(self):
		signal.signal(signal.SIGINT, signal.SIG_DFL)
		gtk.main()

if __name__ == "__main__":
	if len(sys.argv) != 2:
		print 'Error: you need to supply the URL to your config file as the second parameter'
		sys.exit(1)

	CONFIG_URL = sys.argv[1]
	DEBUG = 'localhost' in CONFIG_URL
	StatsPi().main()
