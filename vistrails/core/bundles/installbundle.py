############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################

"""Module with utilities to try and install a bundle if possible."""

from core.bundles.utils import guess_system, guess_graphical_sudo
import core.bundles.installbundle # this is on purpose
import os

##############################################################################

def has_qt():
    try:
        import PyQt4
        # Must import this on Ubuntu linux, because PyQt4 doesn't come with
        # PyQt4.QtOpenGL by default
        import PyQt4.QtOpenGL
        has_qt = True
    except ImportError:
        has_qt = False

def linux_ubuntu_install(package_name):
    
    qt = has_qt()
    # HACK, otherwise splashscreen stays in front of windows
    if qt():
        try:
            import PyQt4.QtCore
            PyQt4.QtCore.QCoreApplication.instance().splashScreen.hide()
        except:
            pass
        
    if qt:
        cmd = core.system.vistrails_root_directory()
        cmd += '/core/bundles/linux_ubuntu_install.py'
    else:
        cmd = 'apt-get install'

    if type(package_name) == str:
        cmd += ' ' + package_name
    elif type(package_name) == list:
        for package in package_name:
            if type(package) != str:
                raise TypeError("Expected string or list of strings")
            cmd += ' ' + package

    if qt:
        sucmd = guess_graphical_sudo() + " '" + cmd + "'"
    else:
        print "VisTrails wants to install package(s) '%s'" % package_name
        sucmd = "sudo " + cmd

    result = os.system(sucmd)

    return (result == 0) # 0 indicates success

def show_question():
    qt = has_qt()
    if qt:
        import gui.utils
        v = gui.utils.show_question("Required package missing",
                                    "A required package is missing, but VisTrails can " +
                                    "automaticallly install it. " +
                                    "If you click OK, VisTrails will need "+
                                    "administrator privileges, and you" +
                                    "might be asked for the administrator password.",
                                    buttons=[gui.utils.OK_BUTTON,
                                             gui.utils.CANCEL_BUTTON],
                                    default=gui.utils.OK_BUTTON)
        return v == gui.utils.OK_BUTTON
    else:
        print "Required package missing"
        print ("A required package is missing, but VisTrails can " +
               "automaticallly install it. " +
               "If you say Yes, VisTrails will need "+
               "administrator privileges, and you" +
               "might be asked for the administrator password.")
        print "Give VisTrails permission to try to install package? (Y/n)"
        v = raw_input().upper()
        return v == 'Y' or v == 'YES'


def install(dependency_dictionary):
    """Tries to import a python module. If unsuccessful, tries to install
the appropriate bundle and then reimport. py_import tries to be smart
about which system it runs on."""

    # Ugly fix to avoid circular import
    distro = guess_system()
    if not dependency_dictionary.has_key(distro):
        return False
    else:
        if show_question():
            callable_ = getattr(core.bundles.installbundle,
                                distro.replace('-', '_') + '_install')
            return callable_(dependency_dictionary[distro])
        else:
            return False
