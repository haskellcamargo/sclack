#!/usr/bin/env python3
import curses
import curses.panel
import sys

def app(stdscr):
    key = 0
    sidebar = curses.newpad(curses.LINES, 27)
    while key != ord('q'):
        stdscr.box()
        stdscr.bkgd(' ', curses.color_pair(2))
        stdscr.refresh()
        sidebar.box()
        sidebar.bkgd('~', curses.color_pair(1))
        sidebar.refresh( 0, 0, 0, 0, curses.LINES - 1, 26)
        key = stdscr.getch()

curses.initscr()

# init additional 8 colors
for i in range(0, 255):
    intesity = (1000*i/255)
    try:
        curses.init_color(i, intesity, 0, 0)
    except:
        print("Failed to initialize pair #%d".format(i))

# init color pairs
for i in range(1, 255):
    try:
        curses.init_pair(i, i, 0)
    except:
        print("Failed to initialize pair #%d".format(i))
        pass

curses.start_color()
curses.init_pair(1, 165, 53)
curses.init_pair(2, 240, 253)
curses.wrapper(app)
