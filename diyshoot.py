"""
Tool to facilitate book digitization with the DIY BookScanner.

Copyright (c) 2013 Johannes Baiter. All rights reserved.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import argparse
import logging
import multiprocessing
import os
import re
import subprocess
import sys
import time

from clint.textui import puts, colored

logging.basicConfig(level=logging.DEBUG)

# Kudos to http://stackoverflow.com/a/1394994/487903
try:
    from msvcrt import getch
except ImportError:
    def getch():
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_parallel(jobs):
    running = []
    for job in jobs:
        p = multiprocessing.Process(target=job['func'],
                                    args=job['args'],
                                    kwargs=job['kwargs'])
        running.append(p)
        p.start()
    for proc in running:
        proc.join()


class Camera(object):
    def __init__(self, usb_port):
        self._port = usb_port
        self.orientation = (self._gphoto2(["--get-config",
                                           "/main/settings/ownername"])
                            .split("\n")[-2][9:])

    def _gphoto2(self, args):
        cmd = (["gphoto2", "--port", self._port] + args)
        logging.debug("Running " + " ".join(cmd))
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return out

    def _ptpcam(self, command):
        bus, device = self._port[4:].split(',')
        cmd = ["/usr/bin/ptpcam", "--dev={0}".format(device),
               "--bus={0}".format(bus),
               "--chdk='{0}'".format(command)]
        logging.debug("Running " + " ".join(cmd))
        out = subprocess.check_output(" ".join(cmd), shell=True,
                                      stderr=subprocess.STDOUT)
        return out

    def set_orientation(self, orientation):
        self._gphoto2(["--set-config",
                       "/main/settings/ownername={0}".format(orientation)])
        self.orientation = orientation

    def delete_files(self):
        try:
            self._gphoto2(["--recurse", "-D", "A/store00010001/DCIM/"])
        except subprocess.CalledProcessError:
            # For some reason gphoto2 throws an error despite everything going
            # well...
            pass

    def download_files(self, path):
        cur_dir = os.getcwd()
        if not os.path.exists(path):
            os.mkdir(path)
        os.chdir(path)
        try:
            self._gphoto2(["--recurse", "-P", "A/store00010001/DCIM/"])
        except subprocess.CalledProcessError:
            # For some reason gphoto2 throws an error despite everything going
            # well...
            pass
        os.chdir(cur_dir)

    def set_record_mode(self):
        self._ptpcam("mode 1")

    def set_zoom(self, level=3):
        # TODO: Cross-check with zoom-value obtained via get_zoom to avoid
        #       superfluous presses
        # TODO: Wait some time before the first press, this way we can skip
        #       the +1 on the xrange
        # TODO: See if we can lower the time sleeping between zoom steps
        for x in xrange(level+1):
            self._ptpcam('luar click("zoom_in")')
            time.sleep(1)
            print self._ptpcam('luar get_zoom()')

    def disable_flash(self):
        self._ptpcam("luar set_prop(16, 2)")

    def set_iso(self, iso_value=373):
        self._ptpcam("luar set_sv96({0})".format(iso_value))

    def disable_ndfilter(self):
        self._ptpcam("luar set_nd_filter(2)")

    def shoot(self, shutter_speed=320, iso_value=373):
        """ Values for shutter speed are as follows:
            http://chdk.wikia.com/wiki/CHDK_scripting#set_tv96_direct
        """
        # Set shutter speed (has to be set for every shot)
        self._ptpcam("luar set_sv96({0})".format(iso_value))
        self._ptpcam("luar set_tv96_direct({0})".format(shutter_speed))
        self._ptpcam("luar shoot()")

    def play_sound(self, sound_num):
        """ Plays one of the following sounds:
                0 = startup sound
                1 = shutter sound
                2 = button press sound
                3 = selftimer
                4 = short beep
                5 = af (auto focus) confirmation
                6 = error beep
        """
        self._ptpcam("lua play_sound({1})".format(sound_num))


def detect_cameras():
    cams = [Camera(re.search(r'usb:\d+,\d+', x).group()) for x in
            (subprocess.check_output(['gphoto2', '--auto-detect'])
                .split('\n')[2:-1])
            ]
    return cams


def shoot(args):
    puts("Starting scanning workflow, please connect the cameras.")
    puts(colored.blue("Press any key to continue."))
    getch()
    puts("Detecting cameras.")
    cameras = detect_cameras()
    puts(colored.green("Found {0} cameras!".format(len(cameras))))
    # Set up for shooting
    for camera in cameras:
        puts("Setting up {0} camera.".format(camera.orientation))
        camera.set_record_mode()
        camera.set_zoom()
        camera.set_iso()
        camera.disable_flash()
        camera.disable_ndfilter()
    # Start shooting loop
    puts(colored.blue("Press 'b' or the footpedal to shoot."))
    shot_count = 0
    start_time = time.time()
    while True:
        if getch() != 'b':
            break
        run_parallel([{'func': x.shoot, 'args': [],
                      'kwargs': {'shutter_speed': 448}}
                      for x in cameras])
        shot_count += len(cameras)
        pages_per_hour = (3600/(time.time() - start_time))*shot_count
        status = "{0} pages [{1}/h]\r".format(colored.blue(
                                              sum(shot_count.values())),
                                              pages_per_hour)
        sys.stdout.write(status)
        sys.stdout.flush()


def download(args):
    destination = args.destination
    if not os.path.exists(destination):
        os.mkdir(destination)
    cameras = detect_cameras()
    run_parallel([{'func': x.download_files,
                   'args': [os.path.join(destination. camera.orientation)],
                   'kwargs': {}} for x in cameras])
    run_parallel([{'func': x.delete_files, 'args': [], 'kwargs': {}}
                  for x in cameras])


def calibrate(args):
    # TODO: Calculate DPI from grid and set it in the JPGs
    # TODO: Dewarp the pictures
    # TODO: Rotate the pictures depending on orientation
    raise NotImplementedError


def merge(args):
    # TODO: Merge folders 'left' and 'right' into one 'combined' folder while
    #       preserving the page order
    # TODO: Warn if the folder's have a different number of pages
    raise NotImplementedError

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scanning Tool for  DIY Book"
                                     "Scanner")
    subparsers = parser.add_subparsers()

    shoot_parser = subparsers.add_parser('shoot',
                                         help="Start the shooting workflow")
    shoot_parser.set_defaults(func=shoot)
    download_parser = subparsers.add_parser('download',
                                            help="Download scanned images.")
    download_parser.add_argument("-d", "--destination", help="Path where"
                                 "scanned images will be stored")
    download_parser.set_defaults(func=download)
    args = parser.parse_args()
    args.func(args)
