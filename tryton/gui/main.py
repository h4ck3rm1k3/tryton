#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import os
import gettext
import urlparse
import gobject
import gtk
from gtk import glade
import tryton.rpc as rpc
from tryton.config import CONFIG, GLADE, TRYTON_ICON, PIXMAPS_DIR, DATA_DIR
import tryton.common as common
from tryton.action import Action
from tryton.gui.window import Window
from tryton.gui.window.preference import Preference
from tryton.gui.window import FilesActions
from tryton.gui.window.dblogin import DBLogin
from tryton.gui.window.dbcreate import DBCreate
from tryton.gui.window.tips import Tips
from tryton.gui.window.about import About
from tryton.gui.window.shortcuts import Shortcuts
import re
import base64
import tryton.translate as translate
import tryton.plugin
import pango

_ = gettext.gettext


_MAIN = []

class Main(object):
    window = None

    def __init__(self):
        super(Main, self).__init__()

        self.window = gtk.Window()
        self.window.set_default_size(900, 750)
        self.window.set_title('Tryton')
        self.window.set_icon(TRYTON_ICON)
        self.window.connect("destroy", Main.sig_quit)
        self.window.connect("delete_event", self.sig_delete)

        self.accel_group = gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        self.tooltips = gtk.Tooltips()

        toolbar = gtk.Toolbar()
        self.toolbar = toolbar
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_BOTH)

        vbox = gtk.VBox()
        self.window.add(vbox)

        menubar = gtk.MenuBar()
        vbox.pack_start(menubar, False, True)

        menuitem_file = gtk.MenuItem(_('_File'))
        menubar.add(menuitem_file)

        menu_file = self._set_menu_file()
        menuitem_file.set_submenu(menu_file)

        menuitem_user = gtk.MenuItem(_('_User'))
        self.menuitem_user = menuitem_user
        menuitem_user.set_sensitive(False)
        menubar.add(menuitem_user)

        menu_user = self._set_menu_user()
        menuitem_user.set_submenu(menu_user)

        menuitem_form = gtk.MenuItem(_('For_m'))
        self.menuitem_form = menuitem_form
        menuitem_form.set_sensitive(False)
        menubar.add(menuitem_form)

        menu_form = self._set_menu_form()
        menuitem_form.set_submenu(menu_form)

        menuitem_options = gtk.MenuItem(_('_Options'))
        menubar.add(menuitem_options)

        menu_options = self._set_menu_options()
        menuitem_options.set_submenu(menu_options)

        menuitem_plugins = gtk.MenuItem(_('_Plugins'))
        self.menuitem_plugins = menuitem_plugins
        self.menuitem_plugins.set_sensitive(False)
        menubar.add(menuitem_plugins)

        menu_plugins = self._set_menu_plugins()
        menuitem_plugins.set_submenu(menu_plugins)

        menuitem_shortcut = gtk.MenuItem(_('_Shortcuts'))
        self.menuitem_shortcut = menuitem_shortcut
        self.menuitem_shortcut.set_sensitive(False)
        menubar.add(menuitem_shortcut)

        menuitem_help = gtk.MenuItem(_('_Help'))
        menubar.add(menuitem_help)

        menu_help = self._set_menu_help()
        menuitem_help.set_submenu(menu_help)

        vbox.pack_start(toolbar, False, True)

        self.buttons = {}
        self._set_toolbar()

        self.notebook = gtk.Notebook()
        self.notebook.popup_enable()
        self.notebook.set_scrollable(True)
        self.notebook.connect_after('switch-page', self._sig_page_changt)
        vbox.pack_start(self.notebook, True, True)

        self.status_hbox = gtk.HBox(spacing=2)
        vbox.pack_start(self.status_hbox, False, True, padding=2)

        self.sb_servername = gtk.Statusbar()
        self.sb_servername.set_size_request(150, -1)
        self.sb_servername.set_has_resize_grip(False)
        self.status_hbox.pack_start(self.sb_servername, True, True)
        sb_id = self.sb_servername.get_context_id('message')
        self.sb_servername.push(sb_id, _('Press Ctrl+O to login'))

        self.sb_username = gtk.Statusbar()
        self.sb_username.set_size_request(130, -1)
        self.sb_username.set_has_resize_grip(False)
        self.status_hbox.pack_start(self.sb_username, True, True)

        self.status_hbox.pack_start(gtk.Label(_('Requests:')), False, True)

        self.sb_requests = gtk.Statusbar()
        self.sb_requests.set_size_request(130, -1)
        self.sb_requests.set_has_resize_grip(False)
        self.status_hbox.pack_start(self.sb_requests, True, True)

        button_request_new = gtk.Button()
        self.button_request_new = button_request_new
        image = gtk.Image()
        image.set_from_stock('tryton-mail-message-new', gtk.ICON_SIZE_MENU)
        button_request_new.set_image(image)
        button_request_new.set_relief(gtk.RELIEF_NONE)
        button_request_new.connect('clicked', self.sig_request_new)
        button_request_new.set_sensitive(False)
        self.tooltips.set_tip(button_request_new, _('Send a new request'))
        self.status_hbox.pack_start(button_request_new, False, True)

        button_request_search = gtk.Button()
        self.button_request_search = button_request_search
        image = gtk.Image()
        image.set_from_stock('tryton-find', gtk.ICON_SIZE_MENU)
        button_request_search.set_image(image)
        button_request_search.set_relief(gtk.RELIEF_NONE)
        button_request_search.connect('clicked', self.sig_request_open)
        button_request_search.set_sensitive(False)
        self.tooltips.set_tip(button_request_search, _('Read my Requests'))
        self.status_hbox.pack_start(button_request_search, False, True)

        self.secure_img = gtk.Image()
        self.secure_img.set_from_stock('tryton-lock', gtk.ICON_SIZE_MENU)
        self.status_hbox.pack_start(self.secure_img, False, True)

        self.window.show_all()

        self.pages = []
        self.previous_pages = {}
        self.current_page = 0
        self.last_page = 0

        if CONFIG['client.modepda']:
            self.radiomenuitem_pda.set_active(True)
        else:
            self.radiomenuitem_normal.set_active(True)
        self.sb_set()

        settings = gtk.settings_get_default()
        settings.set_long_property('gtk-button-images', 1, 'Tryton:gui.main')

        self.sig_mode()

        if os.name in ('nt', 'mac') or os.uname()[0] == 'Darwin':
            # Disable actions, on win32 we use os.startfile
            # and on mac we use /usr/bin/open
            self.menuitem_actions.set_sensitive(False)

        # Adding a timer the check to requests
        gobject.timeout_add(5 * 60 * 1000, self.request_set)
        _MAIN.append(self)

    def _set_menu_file(self):
        menu_file = gtk.Menu()

        imagemenuitem_connect = gtk.ImageMenuItem(_('_Connect...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-connect', gtk.ICON_SIZE_MENU)
        imagemenuitem_connect.set_image(image)
        imagemenuitem_connect.add_accelerator('activate', self.accel_group,
                gtk.keysyms.O, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_connect.connect('activate', self.sig_login)
        menu_file.add(imagemenuitem_connect)

        imagemenuitem_disconnect = gtk.ImageMenuItem(_('_Disconnect...'))
        image = gtk.Image()
        image.set_from_stock('tryton-disconnect', gtk.ICON_SIZE_MENU)
        imagemenuitem_disconnect.set_image(image)
        imagemenuitem_disconnect.connect('activate', self.sig_logout)
        menu_file.add(imagemenuitem_disconnect)

        menu_file.add(gtk.SeparatorMenuItem())

        imagemenuitem_database = gtk.ImageMenuItem(_('Data_base'))
        image = gtk.Image()
        image.set_from_stock('tryton-system-file-manager', gtk.ICON_SIZE_MENU)
        imagemenuitem_database.set_image(image)
        menu_file.add(imagemenuitem_database)

        menu_database = gtk.Menu()
        imagemenuitem_database.set_submenu(menu_database)

        imagemenuitem_db_new = gtk.ImageMenuItem(_('_New Database'))
        image = gtk.Image()
        image.set_from_stock('tryton-folder-new', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_new.set_image(image)
        imagemenuitem_db_new.connect('activate', self.sig_db_new)
        menu_database.add(imagemenuitem_db_new)

        imagemenuitem_db_restore = gtk.ImageMenuItem(_('_Restore Database'))
        image = gtk.Image()
        image.set_from_stock('tryton-folder-saved-search', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_restore.set_image(image)
        imagemenuitem_db_restore.connect('activate', self.sig_db_restore)
        menu_database.add(imagemenuitem_db_restore)

        imagemenuitem_db_dump = gtk.ImageMenuItem(_('_Backup Database'))
        image = gtk.Image()
        image.set_from_stock('tryton-save-as', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_dump.set_image(image)
        imagemenuitem_db_dump.connect('activate', self.sig_db_dump)
        menu_database.add(imagemenuitem_db_dump)

        imagemenuitem_db_drop = gtk.ImageMenuItem(_('Dro_p Database'))
        image = gtk.Image()
        image.set_from_stock('tryton-delete', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_drop.set_image(image)
        imagemenuitem_db_drop.connect('activate', self.sig_db_drop)
        menu_database.add(imagemenuitem_db_drop)

        menu_database.add(gtk.SeparatorMenuItem())

        imagemenuitem_db_password = gtk.ImageMenuItem(_('_Administrator Password'))
        image = gtk.Image()
        image.set_from_stock('tryton-users', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_password.set_image(image)
        imagemenuitem_db_password.connect('activate', self.sig_db_password)
        menu_database.add(imagemenuitem_db_password)

        menu_file.add(gtk.SeparatorMenuItem())

        imagemenuitem_close = gtk.ImageMenuItem(_('_Quit'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-log-out', gtk.ICON_SIZE_MENU)
        imagemenuitem_close.set_image(image)
        imagemenuitem_close.add_accelerator('activate', self.accel_group,
                gtk.keysyms.Q, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_close.connect('activate', self.sig_close)
        menu_file.add(imagemenuitem_close)
        return menu_file

    def _set_menu_user(self):
        menu_user = gtk.Menu()

        imagemenuitem_preference = gtk.ImageMenuItem(_('_Preferences'))
        image = gtk.Image()
        image.set_from_stock('tryton-preferences-system-session',
                gtk.ICON_SIZE_MENU)
        imagemenuitem_preference.set_image(image)
        imagemenuitem_preference.connect('activate', self.sig_user_preferences)
        menu_user.add(imagemenuitem_preference)

        menu_user.add(gtk.SeparatorMenuItem())

        imagemenuitem_send_request = gtk.ImageMenuItem(_('_Send a Request'))
        image = gtk.Image()
        image.set_from_stock('tryton-mail-message-new', gtk.ICON_SIZE_MENU)
        imagemenuitem_send_request.set_image(image)
        imagemenuitem_send_request.connect('activate', self.sig_request_new)
        menu_user.add(imagemenuitem_send_request)

        imagemenuitem_open_request = gtk.ImageMenuItem(_('_Read my Requests'))
        image = gtk.Image()
        image.set_from_stock('tryton-find', gtk.ICON_SIZE_MENU)
        imagemenuitem_open_request.set_image(image)
        imagemenuitem_open_request.connect('activate', self.sig_request_open)
        menu_user.add(imagemenuitem_open_request)
        return menu_user

    def _set_menu_form(self):
        menu_form = gtk.Menu()

        imagemenuitem_new = gtk.ImageMenuItem(_('_New'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-new', gtk.ICON_SIZE_MENU)
        imagemenuitem_new.set_image(image)
        imagemenuitem_new.add_accelerator('activate', self.accel_group,
                gtk.keysyms.N, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_new.connect('activate', self._sig_child_call, 'but_new')
        menu_form.add(imagemenuitem_new)

        imagemenuitem_save = gtk.ImageMenuItem(_('_Save'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-save', gtk.ICON_SIZE_MENU)
        imagemenuitem_save.set_image(image)
        imagemenuitem_save.add_accelerator('activate', self.accel_group,
                gtk.keysyms.S, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_save.connect('activate', self._sig_child_call, 'but_save')
        menu_form.add(imagemenuitem_save)

        imagemenuitem_copy = gtk.ImageMenuItem(_('_Duplicate'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-copy', gtk.ICON_SIZE_MENU)
        imagemenuitem_copy.set_image(image)
        imagemenuitem_copy.add_accelerator('activate', self.accel_group,
                gtk.keysyms.D, gtk.gdk.CONTROL_MASK|gtk.gdk.SHIFT_MASK,
                gtk.ACCEL_VISIBLE)
        imagemenuitem_copy.connect('activate', self._sig_child_call, 'but_copy')
        menu_form.add(imagemenuitem_copy)

        imagemenuitem_delete = gtk.ImageMenuItem(_('_Delete'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-delete', gtk.ICON_SIZE_MENU)
        imagemenuitem_delete.set_image(image)
        imagemenuitem_delete.add_accelerator('activate', self.accel_group,
                gtk.keysyms.D, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_delete.connect('activate', self._sig_child_call, 'but_remove')
        menu_form.add(imagemenuitem_delete)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_search = gtk.ImageMenuItem(_('_Find'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-find', gtk.ICON_SIZE_MENU)
        imagemenuitem_search.set_image(image)
        imagemenuitem_search.add_accelerator('activate', self.accel_group,
                gtk.keysyms.F, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_search.connect('activate', self._sig_child_call, 'but_search')
        menu_form.add(imagemenuitem_search)

        imagemenuitem_next = gtk.ImageMenuItem(_('_Next'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-next', gtk.ICON_SIZE_MENU)
        imagemenuitem_next.set_image(image)
        imagemenuitem_next.add_accelerator('activate', self.accel_group,
                gtk.keysyms.Page_Down, 0, gtk.ACCEL_VISIBLE)
        imagemenuitem_next.connect('activate', self._sig_child_call, 'but_next')
        menu_form.add(imagemenuitem_next)

        imagemenuitem_previous = gtk.ImageMenuItem(_('_Previous'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-previous', gtk.ICON_SIZE_MENU)
        imagemenuitem_previous.set_image(image)
        imagemenuitem_previous.add_accelerator('activate', self.accel_group,
                gtk.keysyms.Page_Up, 0, gtk.ACCEL_VISIBLE)
        imagemenuitem_previous.connect('activate', self._sig_child_call, 'but_previous')
        menu_form.add(imagemenuitem_previous)

        imagemenuitem_previous = gtk.ImageMenuItem(_('_Previous'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-previous', gtk.ICON_SIZE_MENU)
        imagemenuitem_previous.set_image(image)
        imagemenuitem_previous.add_accelerator('activate', self.accel_group,
                gtk.keysyms.Page_Up, 0, gtk.ACCEL_VISIBLE)
        imagemenuitem_previous.connect('activate', self._sig_child_call, 'but_previous')
        menu_form.add(imagemenuitem_previous)

        imagemenuitem_switch = gtk.ImageMenuItem(_('_Switch View'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-fullscreen', gtk.ICON_SIZE_MENU)
        imagemenuitem_switch.set_image(image)
        imagemenuitem_switch.add_accelerator('activate', self.accel_group,
                gtk.keysyms.L, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_switch.connect('activate', self._sig_child_call, 'but_switch')
        menu_form.add(imagemenuitem_switch)

        imagemenuitem_menu = gtk.ImageMenuItem(_('_Menu'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-start-here', gtk.ICON_SIZE_MENU)
        imagemenuitem_menu.set_image(image)
        imagemenuitem_menu.add_accelerator('activate', self.accel_group,
                gtk.keysyms.T, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_menu.connect('activate', self.sig_win_menu)
        menu_form.add(imagemenuitem_menu)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_home = gtk.ImageMenuItem(_('_Home'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-home', gtk.ICON_SIZE_MENU)
        imagemenuitem_home.set_image(image)
        imagemenuitem_home.add_accelerator('activate', self.accel_group,
                gtk.keysyms.H, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_home.connect('activate', self.sig_home_new)
        menu_form.add(imagemenuitem_home)

        imagemenuitem_close = gtk.ImageMenuItem(_('_Close'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-close', gtk.ICON_SIZE_MENU)
        imagemenuitem_close.set_image(image)
        imagemenuitem_close.add_accelerator('activate', self.accel_group,
                gtk.keysyms.W, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_close.connect('activate', self.sig_win_close)
        menu_form.add(imagemenuitem_close)

        imagemenuitem_win_prev = gtk.ImageMenuItem(_('_Previous Tab'), self.accel_group)
        imagemenuitem_win_prev.add_accelerator('activate', self.accel_group,
                gtk.keysyms.Page_Up, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_win_prev.connect('activate', self.sig_win_prev)
        menu_form.add(imagemenuitem_win_prev)

        imagemenuitem_win_next = gtk.ImageMenuItem(_('_Next Tab'), self.accel_group)
        imagemenuitem_win_next.add_accelerator('activate', self.accel_group,
                gtk.keysyms.Page_Down, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_win_next.connect('activate', self.sig_win_next)
        menu_form.add(imagemenuitem_win_next)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_log = gtk.ImageMenuItem(_('View _Logs'))
        imagemenuitem_log.connect('activate', self._sig_child_call, 'but_log')
        menu_form.add(imagemenuitem_log)

        imagemenuitem_goto_id = gtk.ImageMenuItem(_('_Go to Record ID...'),
                self.accel_group)
        imagemenuitem_win_next.add_accelerator('activate', self.accel_group,
                gtk.keysyms.G, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_goto_id.connect('activate', self._sig_child_call,
                'but_goto_id')
        menu_form.add(imagemenuitem_goto_id)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_reload = gtk.ImageMenuItem(_('_Reload/Undo'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-refresh', gtk.ICON_SIZE_MENU)
        imagemenuitem_reload.set_image(image)
        imagemenuitem_reload.add_accelerator('activate', self.accel_group,
                gtk.keysyms.R, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_reload.connect('activate', self._sig_child_call,
                'but_reload')
        menu_form.add(imagemenuitem_reload)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_action = gtk.ImageMenuItem(_('_Actions'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-executable', gtk.ICON_SIZE_MENU)
        imagemenuitem_action.set_image(image)
        imagemenuitem_action.add_accelerator('activate', self.accel_group,
                gtk.keysyms.E, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_action.connect('activate', self._sig_child_call,
                'but_action')
        menu_form.add(imagemenuitem_action)

        imagemenuitem_print = gtk.ImageMenuItem(_('_Print'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-print', gtk.ICON_SIZE_MENU)
        imagemenuitem_print.set_image(image)
        imagemenuitem_print.add_accelerator('activate', self.accel_group,
                gtk.keysyms.P, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        imagemenuitem_print.connect('activate', self._sig_child_call,
                'but_print')
        menu_form.add(imagemenuitem_print)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_export = gtk.ImageMenuItem(_('_Export Data...'))
        image = gtk.Image()
        image.set_from_stock('tryton-save-as', gtk.ICON_SIZE_MENU)
        imagemenuitem_export.set_image(image)
        imagemenuitem_export.connect('activate', self._sig_child_call,
                'but_save_as')
        menu_form.add(imagemenuitem_export)

        menuitem_import = gtk.MenuItem(_('_Import Data...'))
        menuitem_import.connect('activate', self._sig_child_call,
                'but_import')
        menu_form.add(menuitem_import)
        return menu_form

    def _set_menu_options(self):
        menu_options = gtk.Menu()

        menuitem_menubar = gtk.MenuItem(_('_Menubar'))
        menu_options.add(menuitem_menubar)

        menu_menubar = gtk.Menu()
        menuitem_menubar.set_submenu(menu_menubar)

        radiomenuitem_default = gtk.RadioMenuItem(label=_('_Default'))
        radiomenuitem_default.connect('activate',
                lambda x: self.sig_menubar('default'))
        menu_menubar.add(radiomenuitem_default)
        if (CONFIG['client.toolbar'] or 'both') == 'default':
            radiomenuitem_default.set_active(True)

        radiomenuitem_both = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Text and Icons'))
        radiomenuitem_both.connect('activate',
                lambda x: self.sig_menubar('both'))
        menu_menubar.add(radiomenuitem_both)
        if (CONFIG['client.toolbar'] or 'both') == 'both':
            radiomenuitem_both.set_active(True)

        radiomenuitem_icons = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Icons'))
        radiomenuitem_icons.connect('activate',
                lambda x: self.sig_menubar('icons'))
        menu_menubar.add(radiomenuitem_icons)
        if (CONFIG['client.toolbar'] or 'both') == 'icons':
            radiomenuitem_icons.set_active(True)

        radiomenuitem_text = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Text'))
        radiomenuitem_text.connect('activate',
                lambda x: self.sig_menubar('text'))
        menu_menubar.add(radiomenuitem_text)
        if (CONFIG['client.toolbar'] or 'both') == 'text':
            radiomenuitem_text.set_active(True)

        menuitem_mode = gtk.MenuItem(_('_Mode'))
        menu_options.add(menuitem_mode)

        menu_mode = gtk.Menu()
        menuitem_mode.set_submenu(menu_mode)

        radiomenuitem_normal = gtk.RadioMenuItem(label=_('_Normal'))
        self.radiomenuitem_normal = radiomenuitem_normal
        radiomenuitem_normal.connect('activate',
                lambda x: self.sig_mode_change(False))
        menu_mode.add(radiomenuitem_normal)

        radiomenuitem_pda = gtk.RadioMenuItem(group=radiomenuitem_normal,
                label=_('_PDA'))
        radiomenuitem_pda.connect('activate',
                lambda x: self.sig_mode_change(True))
        menu_mode.add(radiomenuitem_pda)

        menuitem_form = gtk.MenuItem(_('_Form'))
        menu_options.add(menuitem_form)

        menu_form = gtk.Menu()
        menuitem_form.set_submenu(menu_form)

        checkmenuitem_toolbar = gtk.CheckMenuItem(_('Toolbar'))
        checkmenuitem_toolbar.connect('activate',
                lambda menuitem: self.sig_toolbar(menuitem.get_active()))
        menu_form.add(checkmenuitem_toolbar)
        if CONFIG['form.toolbar']:
            checkmenuitem_toolbar.set_active(True)

        checkmenuitem_tree_width = gtk.CheckMenuItem(_('Save Columns Width'))
        checkmenuitem_tree_width.connect('activate',
                lambda menuitem: CONFIG.__setitem__('client.tree_width',
                    menuitem.get_active()))
        menu_form.add(checkmenuitem_tree_width)
        if CONFIG['client.tree_width']:
            checkmenuitem_tree_width.set_active(True)

        checkmenuitem_spellcheck = gtk.CheckMenuItem(_('Spell Checking'))
        checkmenuitem_spellcheck.connect('activate',
                lambda menuitem: CONFIG.__setitem__('client.spellcheck',
                    menuitem.get_active()))
        menu_form.add(checkmenuitem_spellcheck)
        if CONFIG['client.spellcheck']:
            checkmenuitem_spellcheck.set_active(True)

        menuitem_tab = gtk.MenuItem(_('Tabs Position'))
        menu_form.add(menuitem_tab)

        menu_tab = gtk.Menu()
        menuitem_tab.set_submenu(menu_tab)

        radiomenuitem_top = gtk.RadioMenuItem(label=_('Top'))
        radiomenuitem_top.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'top'))
        menu_tab.add(radiomenuitem_top)
        if (CONFIG['client.form_tab'] or 'left') == 'top':
            radiomenuitem_top.set_active(True)

        radiomenuitem_left = gtk.RadioMenuItem(group=radiomenuitem_top,
                label=_('Left'))
        radiomenuitem_left.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'left'))
        menu_tab.add(radiomenuitem_left)
        if (CONFIG['client.form_tab'] or 'left') == 'left':
            radiomenuitem_left.set_active(True)

        radiomenuitem_right = gtk.RadioMenuItem(group=radiomenuitem_top,
                label=_('Right'))
        radiomenuitem_right.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'right'))
        menu_tab.add(radiomenuitem_right)
        if (CONFIG['client.form_tab'] or 'left') == 'right':
            radiomenuitem_right.set_active(True)

        radiomenuitem_bottom = gtk.RadioMenuItem(group=radiomenuitem_top,
                label=_('Bottom'))
        radiomenuitem_bottom.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'bottom'))
        menu_tab.add(radiomenuitem_bottom)
        if (CONFIG['client.form_tab'] or 'left') == 'bottom':
            radiomenuitem_bottom.set_active(True)

        menuitem_orientation = gtk.MenuItem(_('Tabs Orientation'))
        menu_form.add(menuitem_orientation)

        menu_orientation = gtk.Menu()
        menuitem_orientation.set_submenu(menu_orientation)

        radiomenuitem_horizontal = gtk.RadioMenuItem(label=_('Horizontal'))
        radiomenuitem_horizontal.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab_orientation',
                    0))
        menu_orientation.add(radiomenuitem_horizontal)
        if (str(CONFIG['client.form_tab_orientation']) or '0') == '0':
            radiomenuitem_horizontal.set_active(True)

        radiomenuitem_vertical = gtk.RadioMenuItem(group=radiomenuitem_horizontal,
                label=_('Vertical'))
        radiomenuitem_vertical.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab_orientation',
                    90))
        menu_orientation.add(radiomenuitem_vertical)
        if (str(CONFIG['client.form_tab_orientation']) or '0') == '90':
            radiomenuitem_vertical.set_active(True)

        menuitem_actions = gtk.MenuItem(_('Files _Actions'))
        self.menuitem_actions = menuitem_actions
        menuitem_actions.connect('activate', self.sig_files_actions)
        menu_options.add(menuitem_actions)

        menu_options.add(gtk.SeparatorMenuItem())

        imagemenuitem_opt_save = gtk.ImageMenuItem(_('_Save Options'))
        image = gtk.Image()
        image.set_from_stock('tryton-save', gtk.ICON_SIZE_MENU)
        imagemenuitem_opt_save.set_image(image)
        imagemenuitem_opt_save.connect('activate', lambda x: CONFIG.save())
        menu_options.add(imagemenuitem_opt_save)
        return menu_options

    def _set_menu_plugins(self):
        menu_plugins = gtk.Menu()

        imagemenuitem_plugin_execute = gtk.ImageMenuItem(_('_Execute a Plugin'))
        image = gtk.Image()
        image.set_from_stock('tryton-executable', gtk.ICON_SIZE_MENU)
        imagemenuitem_plugin_execute.set_image(image)
        imagemenuitem_plugin_execute.connect('activate', self.sig_plugin_execute)
        menu_plugins.add(imagemenuitem_plugin_execute)
        return menu_plugins

    def _set_menu_help(self):
        menu_help = gtk.Menu()

        imagemenuitem_tips = gtk.ImageMenuItem(_('_Tips'))
        image = gtk.Image()
        image.set_from_stock('tryton-information', gtk.ICON_SIZE_MENU)
        imagemenuitem_tips.set_image(image)
        imagemenuitem_tips.connect('activate', self.sig_tips)
        menu_help.add(imagemenuitem_tips)

        imagemenuitem_shortcuts = gtk.ImageMenuItem(_('_Keyboard Shortcuts'))
        image = gtk.Image()
        image.set_from_stock('tryton-help', gtk.ICON_SIZE_MENU)
        imagemenuitem_shortcuts.set_image(image)
        imagemenuitem_shortcuts.connect('activate', self.sig_shortcuts)
        menu_help.add(imagemenuitem_shortcuts)

        menu_help.add(gtk.SeparatorMenuItem())

        imagemenuitem_about = gtk.ImageMenuItem(_('_About'))
        image = gtk.Image()
        image.set_from_stock('gtk-about', gtk.ICON_SIZE_MENU)
        imagemenuitem_about.set_image(image)
        imagemenuitem_about.connect('activate', self.sig_about)
        menu_help.add(imagemenuitem_about)
        return menu_help

    def _set_toolbar(self):
        toolbutton_new = gtk.ToolButton('tryton-new')
        toolbutton_new.set_use_underline(True)
        toolbutton_new.set_label(_('_New'))
        self.toolbar.insert(toolbutton_new, -1)
        toolbutton_new.connect('clicked', self._sig_child_call, 'but_new')
        self.tooltips.set_tip(toolbutton_new, _('Create a new record'))
        self.buttons['but_new'] = toolbutton_new

        toolbutton_save = gtk.ToolButton('tryton-save')
        toolbutton_save.set_use_underline(True)
        toolbutton_save.set_label(_('_Save'))
        self.toolbar.insert(toolbutton_save, -1)
        toolbutton_save.connect('clicked', self._sig_child_call, 'but_save')
        self.tooltips.set_tip(toolbutton_save, _('Save this record'))
        self.buttons['but_save'] = toolbutton_save

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_remove = gtk.ToolButton('tryton-delete')
        toolbutton_remove.set_use_underline(True)
        toolbutton_remove.set_label(_('_Delete'))
        self.toolbar.insert(toolbutton_remove, -1)
        toolbutton_remove.connect('clicked', self._sig_child_call, 'but_remove')
        self.tooltips.set_tip(toolbutton_remove, _('Delete this record'))
        self.buttons['but_remove'] = toolbutton_remove

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_search = gtk.ToolButton('tryton-find')
        toolbutton_search.set_use_underline(True)
        toolbutton_search.set_label(_('_Find'))
        self.toolbar.insert(toolbutton_search, -1)
        toolbutton_search.connect('clicked', self._sig_child_call, 'but_search')
        self.tooltips.set_tip(toolbutton_search, _('Find records'))
        self.buttons['but_search'] = toolbutton_search

        toolbutton_previous = gtk.ToolButton('tryton-go-previous')
        toolbutton_previous.set_label(_('Previous'))
        self.toolbar.insert(toolbutton_previous, -1)
        toolbutton_previous.connect('clicked', self._sig_child_call, 'but_previous')
        self.buttons['but_previous'] = toolbutton_previous

        toolbutton_next = gtk.ToolButton('tryton-go-next')
        toolbutton_next.set_label(_('Next'))
        self.toolbar.insert(toolbutton_next, -1)
        toolbutton_next.connect('clicked', self._sig_child_call, 'but_next')
        self.buttons['but_next'] = toolbutton_next

        toolbutton_switch = gtk.ToolButton('tryton-fullscreen')
        toolbutton_switch.set_label(_('Switch'))
        self.toolbar.insert(toolbutton_switch, -1)
        toolbutton_switch.connect('clicked', self._sig_child_call, 'but_switch')
        self.tooltips.set_tip(toolbutton_switch, _('Switch view'))
        self.buttons['but_switch'] = toolbutton_switch

        toolbutton_reload = gtk.ToolButton('tryton-refresh')
        toolbutton_reload.set_use_underline(True)
        toolbutton_reload.set_label(_('_Reload'))
        self.toolbar.insert(toolbutton_reload, -1)
        toolbutton_reload.connect('clicked', self._sig_child_call, 'but_reload')
        self.buttons['but_reload'] = toolbutton_reload

        toolbutton_menu = gtk.ToolButton('tryton-start-here')
        self.toolbutton_menu = toolbutton_menu
        toolbutton_menu.set_label(_('Menu'))
        self.toolbar.insert(toolbutton_menu, -1)
        toolbutton_menu.connect('clicked', self.sig_win_menu)

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_action = gtk.ToolButton('tryton-executable')
        toolbutton_action.set_label(_('Action'))
        self.toolbar.insert(toolbutton_action, -1)
        toolbutton_action.connect('clicked', self._sig_child_call, 'but_action')
        self.buttons['but_action'] = toolbutton_action

        toolbutton_action = gtk.ToolButton('tryton-print')
        toolbutton_action.set_label(_('Print'))
        self.toolbar.insert(toolbutton_action, -1)
        toolbutton_action.connect('clicked', self._sig_child_call, 'but_print')
        self.buttons['but_print'] = toolbutton_action

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_attach = gtk.ToolButton('tryton-attachment')
        toolbutton_attach.set_label(_('Attachment(0)'))
        self.toolbar.insert(toolbutton_attach, -1)
        toolbutton_attach.connect('clicked', self._sig_child_call, 'but_attach')
        self.tooltips.set_tip(toolbutton_attach, _('Add an attachment to the record'))
        self.buttons['but_attach'] = toolbutton_attach

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_close = gtk.ToolButton('tryton-close')
        toolbutton_close.set_label(_('Close'))
        self.toolbar.insert(toolbutton_close, -1)
        toolbutton_close.connect('clicked', self._sig_child_call, 'but_close')
        self.tooltips.set_tip(toolbutton_close, _('Close the tab'))
        self.buttons['but_close'] = toolbutton_close

    @staticmethod
    def get_main():
        return _MAIN[0]

    def shortcut_set(self, shortcuts=None):
        def _action_shortcut(widget, action):
            Action.exec_keyword('tree_open', self.window, {
                'model': 'ir.ui.menu',
                'id': action,
                'ids': [action],
                })
        if shortcuts is None:
            user = rpc._USER
            try:
                shortcuts = rpc.execute('object', 'execute',
                        'ir.ui.view_sc', 'get_sc', user, 'ir.ui.menu',
                        rpc.CONTEXT)
            except:
                shortcuts = []
        menu = gtk.Menu()
        for shortcut in shortcuts:
            menuitem = gtk.MenuItem(shortcut['name'])
            menuitem.connect('activate', _action_shortcut, shortcut['res_id'])
            menu.add(menuitem)
        menu.show_all()
        self.menuitem_shortcut.set_submenu(menu)
        self.menuitem_shortcut.set_sensitive(True)

    def shortcut_unset(self):
        menu = gtk.Menu()
        menu.show_all()
        self.menuitem_shortcut.set_submenu(menu)
        self.menuitem_shortcut.set_sensitive(False)

    def sig_toolbar(self, value):
        CONFIG['form.toolbar'] = value
        if value:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def sig_mode_change(self, pda_mode=False):
        CONFIG['client.modepda'] = pda_mode
        return self.sig_mode()

    def sig_mode(self):
        pda_mode = CONFIG['client.modepda']
        if pda_mode:
            self.status_hbox.hide()
        else:
            self.status_hbox.show()
        return pda_mode

    def sig_menubar(self, option):
        CONFIG['client.toolbar'] = option
        if option == 'default':
            self.toolbar.set_style(False)
        elif option == 'both':
            self.toolbar.set_style(gtk.TOOLBAR_BOTH)
        elif option == 'text':
            self.toolbar.set_style(gtk.TOOLBAR_TEXT)
        elif option == 'icons':
            self.toolbar.set_style(gtk.TOOLBAR_ICONS)

    @staticmethod
    def sig_form_tab(option):
        CONFIG['client.form_tab'] = option

    @staticmethod
    def sig_form_tab_orientation(option):
        CONFIG['client.form_tab_orientation'] = option

    def sig_files_actions(self, widget):
        FilesActions(self.window).run()

    def sig_win_next(self, widget):
        page = self.notebook.get_current_page()
        if page == len(self.pages) - 1:
            page = -1
        self.notebook.set_current_page(page + 1)

    def sig_win_prev(self, widget):
        page = self.notebook.get_current_page()
        self.notebook.set_current_page(page - 1)

    def sig_user_preferences(self, widget):
        win = Preference(rpc._USER, self.window)
        if win.run():
            rpc.context_reload()
            if 'language_direction' in rpc.CONTEXT:
                translate.set_language_direction(
                        rpc.CONTEXT['language_direction'])
            prefs = rpc.execute('object', 'execute', 'res.user',
                    'get_preferences', False, rpc.CONTEXT)
            sb_id = self.sb_username.get_context_id('message')
            self.sb_username.push(sb_id, prefs.get('status_bar', ''))
            if prefs and 'language' in prefs:
                translate.setlang(prefs['language'])
                CONFIG['client.lang'] = prefs['language']
                CONFIG.save()
        self.window.present()
        return True

    def sig_win_close(self, widget):
        self._sig_child_call(widget, 'but_close')

    def sig_request_new(self, widget):
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['active_test'] = False
        return Window.create(None, 'res.request', False, [
            ], 'form', mode=['form', 'tree'], window=self.window,
            context=ctx)

    def sig_request_open(self, widget):
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['active_test'] = False
        try:
            ids1, ids2 = self.request_set(True)
        except Exception, exception:
            if common.process_exception(exception, self.window):
                ids1, ids2 = self.request_set(True)
            else:
                raise
        ids = ids1 + ids2
        return Window.create(False, 'res.request', ids, [
            ], 'form', mode=['tree', 'form'], window=self.window,
            context=ctx)

    def request_set(self, exception=False):
        try:
            if not exception:
                res = rpc.execute('object', 'execute',
                        'res.request', 'request_get')
                if not res:
                    return ([], [])
                ids, ids2 = res
            else:
                ids, ids2 = rpc.execute('object', 'execute',
                        'res.request', 'request_get')
            if len(ids):
                if len(ids) == 1:
                    message = _('%s request') % len(ids)
                else:
                    message = _('%s requests') % len(ids)
            else:
                message = _('No request')
            if len(ids2):
                if len(ids2) == 1:
                    message += _(' - %s request sent') % len(ids2)
                else:
                    message += _(' - %s requests sent') % len(ids2)
            sb_id = self.sb_requests.get_context_id('message')
            self.sb_requests.push(sb_id, message)
            return (ids, ids2)
        except:
            if exception:
                raise
            return ([], [])

    def sig_login(self, widget=None, dbname=False, res=None):
        if not res:
            try:
                dblogin = DBLogin(self.window)
                res = dblogin.run(dbname, self.window)
            except Exception, exception:
                if exception.args == ('QueryCanceled',):
                    return False
                common.process_exception(exception, self.window)
                return
        self.window.present()
        self.sig_logout(widget, disconnect=False)
        try:
            log_response = rpc.login(*res)
        except Exception, exception:
            common.process_exception(exception, self.window)
            return
        self.refresh_ssl()
        if log_response > 0:
            try:
                prefs = rpc.execute('object', 'execute',
                        'res.user', 'get_preferences', False, rpc.CONTEXT)
            except:
                prefs = None
            menu_id = self.sig_win_menu(quiet=False, prefs=prefs)
            if menu_id:
                self.sig_home_new(quiet=True, except_id=menu_id, prefs=prefs)
            self.request_set()
            if prefs and 'language' in prefs:
                translate.setlang(prefs['language'], prefs.get('locale'))
                CONFIG['client.lang'] = prefs['language']
            CONFIG.save()
        elif log_response == -1:
            common.message(_('Connection error!\n' \
                    'Unable to connect to the server!'), self.window)
        elif log_response == -2:
            common.message(_('Connection error!\n' \
                    'Bad username or password!'), self.window)
            return self.sig_login()
        if not self.menuitem_shortcut.get_property('sensitive'):
            self.shortcut_set()
        self.toolbutton_menu.set_sensitive(True)
        self.menuitem_user.set_sensitive(True)
        self.menuitem_form.set_sensitive(True)
        self.menuitem_plugins.set_sensitive(True)
        self.button_request_new.set_sensitive(True)
        self.button_request_search.set_sensitive(True)
        self.notebook.grab_focus()
        return True

    def sig_logout(self, widget, disconnect=True):
        res = True
        while res:
            wid = self._wid_get()
            if wid:
                if 'but_close' in wid.handlers:
                    res = wid.handlers['but_close']()
                if not res:
                    return False
                res = self._win_del()
            else:
                res = False
        sb_id = self.sb_requests.get_context_id('message')
        self.sb_requests.push(sb_id, '')
        sb_id = self.sb_username.get_context_id('message')
        self.sb_username.push(sb_id, _('Not logged!'))
        sb_id = self.sb_servername.get_context_id('message')
        self.sb_servername.push(sb_id, _('Press Ctrl+O to login'))
        self.shortcut_unset()
        self.toolbutton_menu.set_sensitive(False)
        self.menuitem_user.set_sensitive(False)
        self.menuitem_form.set_sensitive(False)
        self.menuitem_plugins.set_sensitive(False)
        self.button_request_new.set_sensitive(False)
        self.button_request_search.set_sensitive(False)
        if disconnect:
            rpc.logout()
        self.refresh_ssl()
        return True

    def refresh_ssl(self):
        if rpc.SECURE:
            self.tooltips.set_tip(self.secure_img, _('SSL connection') + \
                    '\n' + str(rpc._SOCK.ssl_sock.server()))
            self.secure_img.show()
        else:
            self.tooltips.set_tip(self.secure_img, '')
            self.secure_img.hide()

    def sig_tips(self, *args):
        Tips(self.window)

    def sig_about(self, widget):
        About(self.window)

    def sig_shortcuts(self, widget):
        Shortcuts(self.window).run()

    def sig_win_menu(self, widget=None, quiet=True, prefs=None):
        for page in range(len(self.pages)):
            if self.pages[page].model == 'ir.ui.menu':
                page_num = self.notebook.page_num(self.pages[page].widget)
                self.notebook.set_current_page(page_num)
                return True
        res = self.sig_win_new(widget, menu_type='menu', quiet=quiet,
                prefs=prefs)
        return res

    def sig_win_new(self, widget=None, menu_type='menu', quiet=True,
            except_id=False, prefs=None):
        if not prefs:
            try:
                prefs = rpc.execute('object', 'execute',
                        'res.user', 'get_preferences', False, rpc.CONTEXT)
            except:
                return False
        sb_id = self.sb_username.get_context_id('message')
        self.sb_username.push(sb_id, prefs['status_bar'] or '')
        sb_id = self.sb_servername.get_context_id('message')
        self.sb_servername.push(sb_id, '%s@%s:%d/%s' % (rpc._USERNAME,
            rpc._SOCK.hostname, rpc._SOCK.port, rpc._DATABASE))
        if not prefs[menu_type]:
            if quiet:
                return False
            common.warning(_('You can not log into the system!\n' \
                    'Verify if you have an menu defined on your user.'),
                    'Access Denied!', self.window)
            rpc.logout()
            self.refresh_ssl()
            return False
        act_id = prefs[menu_type]
        if except_id and act_id == except_id:
            return act_id
        Action.execute(act_id, {}, self.window)
        return act_id

    def sig_home_new(self, widget=None, quiet=True, except_id=False,
            prefs=None):
        return self.sig_win_new(widget, menu_type='action', quiet=quiet,
                except_id=except_id, prefs=prefs)

    def sig_plugin_execute(self, widget):
        page = self.notebook.get_current_page()
        datas = {
                'model': self.pages[page].model,
                'ids': self.pages[page].ids_get(),
                'id': self.pages[page].id_get(),
                }
        tryton.plugin.execute(datas, self.window)

    @staticmethod
    def sig_quit(widget):
        CONFIG.save()
        gtk.main_quit()

    def sig_close(self, widget):
        if common.sur(_("Do you really want to quit?"), parent=self.window):
            if not self.sig_logout(widget):
                return False
            CONFIG.save()
            gtk.main_quit()

    def sig_delete(self, widget, event):
        if common.sur(_("Do you really want to quit?"), parent=self.window):
            if not self.sig_logout(widget):
                return True
            return False
        return True

    def win_add(self, page):
        previous_page_id = self.notebook.get_current_page()
        previous_widget = self.notebook.get_nth_page(previous_page_id)
        self.previous_pages[page] = previous_widget
        self.pages.append(page)
        hbox = gtk.HBox()
        name = page.name
        label = gtk.Label(name)
        self.tooltips.set_tip(label, page.name)
        self.tooltips.enable()
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, expand=True, fill=True)
        layout = label.get_layout()
        w, h = layout.get_size()
        icon_w, icon_h = gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR)
        if (w / pango.SCALE) > 120 - icon_w:
            label2 = gtk.Label('...')
            self.tooltips.set_tip(label2, page.name)
            hbox.pack_start(label2, expand=False, fill=False)
        eb = gtk.EventBox()
        self.tooltips.set_tip(eb, _('Close Tab'))
        eb.set_events(gtk.gdk.BUTTON_PRESS)
        eb.set_border_width(1)

        img = gtk.Image()
        img.set_from_stock('tryton-close', gtk.ICON_SIZE_SMALL_TOOLBAR)
        eb.add(img)

        def enter(widget, event, img):
            img.set_from_stock('tryton-close-hi', gtk.ICON_SIZE_SMALL_TOOLBAR)

        def leave(widget, event, img):
            img.set_from_stock('tryton-close', gtk.ICON_SIZE_SMALL_TOOLBAR)

        eb.connect('button_release_event', self._sig_remove_book, page.widget)
        eb.connect('enter_notify_event', enter, img)
        eb.connect('leave_notify_event', leave, img)

        hbox.pack_start(eb, expand=False, fill=False)
        hbox.show_all()
        hbox.set_size_request(120, -1)
        label_menu = gtk.Label(page.name)
        label_menu.set_alignment(0.0, 0.5)
        self.notebook.append_page_menu(page.widget, hbox, label_menu)
        if hasattr(self.notebook, 'set_tab_reorderable'):
            self.notebook.set_tab_reorderable(page.widget, True)
        self.notebook.set_current_page(-1)
        page.signal_connect(self, 'attachment-count', self._attachment_count)

    def sb_set(self, view=None):
        if not view:
            view = self._wid_get()
        for i in self.buttons:
            if self.buttons[i]:
                self.buttons[i].set_sensitive(
                        bool(view and (i in view.handlers)))
        self.buttons['but_attach'].set_stock_id('tryton-attachment')

    def _attachment_count(self, widget, signal_data):
        label = _('Attachment(%d)') % signal_data
        self.buttons['but_attach'].set_label(label)
        if signal_data:
            self.buttons['but_attach'].set_stock_id('tryton-attachment-hi')
        else:
            self.buttons['but_attach'].set_stock_id('tryton-attachment')

    def _sig_remove_book(self, widget, event, page_widget):
        for page in self.pages:
            if page.widget == page_widget:
                if 'but_close' in page.handlers:
                    res = page.handlers['but_close']()
                    if not res:
                        return
        self._win_del(page_widget)

    def _win_del(self, page_widget=None):
        if page_widget:
            page_id = self.notebook.page_num(page_widget)
        else:
            page_id = int(self.notebook.get_current_page())
            page_widget = self.notebook.get_nth_page(page_id)
        if page_id != -1:
            page = None
            for i in range(len(self.pages)):
                if self.pages[i].widget == page_widget:
                    page = self.pages.pop(i)
                    page.signal_unconnect(self)
                    break
            self.notebook.remove_page(page_id)
            self.sb_set()

            next_page_id = -1
            to_pop = []
            for i in self.previous_pages:
                if self.previous_pages[i] == page_widget:
                    to_pop.append(i)
                if i.widget == page_widget:
                    if self.previous_pages[i]:
                        next_page_id = self.notebook.page_num(
                                self.previous_pages[i])
                    to_pop.append(i)
            to_pop.reverse()
            for i in to_pop:
                self.previous_pages.pop(i)

            if hasattr(page, 'destroy'):
                page.destroy()
            del page

            self.notebook.set_current_page(next_page_id)
        return self.notebook.get_current_page() != -1

    def _wid_get(self):
        page_id = self.notebook.get_current_page()
        if page_id == -1:
            return None
        page_widget = self.notebook.get_nth_page(page_id)
        for page in self.pages:
            if page.widget == page_widget:
                return page
        return None

    def _sig_child_call(self, widget, button_name):
        wid = self._wid_get()
        if wid:
            res = True
            if button_name in wid.handlers:
                res = wid.handlers[button_name]()
            if button_name == 'but_close' and res:
                self._win_del()

    def _sig_page_changt(self, notebook, page, page_num):
        self.last_page = self.current_page
        self.current_page = self.notebook.get_current_page()
        title = 'Tryton'
        page = self._wid_get()
        if page:
            title += ' - ' + page.name
        self.window.set_title(title)
        self.sb_set()

    def sig_db_new(self, widget):
        if not self.sig_logout(widget):
            return False
        dia = DBCreate(self.sig_login)
        res = dia.run(self.window)
        if res:
            CONFIG.save()
        return res

    def sig_db_drop(self, widget):
        if not self.sig_logout(widget):
            return False
        url, dbname, passwd = self._choose_db_select(_('Delete a database'))
        if not dbname:
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        host, port = url.rsplit(':', 1)

        try:
            rpc.db_exec(host, int(port), 'drop', passwd, dbname)
        except Exception, exception:
            self.refresh_ssl()
            common.warning(_('Database drop failed with '\
                    'error message:\n') + str(exception[0]), self.window,
                    _('Database drop failed!'))
            return
        self.refresh_ssl()
        common.message(_("Database dropped successfully!"),
                parent=self.window)

    def sig_db_restore(self, widget):
        filename = common.file_selection(_('Open...'), parent=self.window,
                preview=False)
        if not filename:
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        url, dbname, passwd = self._choose_db_ent()
        if dbname:
            file_p = file(filename, 'rb')
            data_b64 = base64.encodestring(file_p.read())
            file_p.close()
            host, port = url.rsplit(':' , 1)
            try:
                res = rpc.db_exec(host, int(port), 'restore', passwd, dbname,
                        data_b64)
            except Exception, exception:
                self.refresh_ssl()
                common.warning(_('Database restore failed with ' \
                        'error message:\n') + str(exception[0]), self.window,
                        _('Database restore failed!'))
                return
            self.refresh_ssl()
            if res:
                common.message(_("Database restored successfully!"),
                        parent=self.window)
            else:
                common.message(_('Database restore failed!'),
                        parent=self.window)
        else:
            rpc.logout()
            Main.get_main().refresh_ssl()

    def sig_db_password(self, widget):
        dialog = glade.XML(GLADE, "dia_passwd_change",
                gettext.textdomain())
        win = dialog.get_widget('dia_passwd_change')
        win.set_icon(TRYTON_ICON)
        win.set_transient_for(self.window)
        win.show_all()
        server_widget = dialog.get_widget('ent_server')
        old_pass_widget = dialog.get_widget('old_passwd')
        new_pass_widget = dialog.get_widget('new_passwd')
        new_pass2_widget = dialog.get_widget('new_passwd2')
        change_button = dialog.get_widget('but_server_change')
        change_button.connect_after('clicked', \
                lambda a,b: common.request_server(b, win), server_widget)

        host = CONFIG['login.server']
        port = int(CONFIG['login.port'])
        url = '%s:%d' % (host, port)
        server_widget.set_text(url)

        res = win.run()
        if res == gtk.RESPONSE_OK:
            url = server_widget.get_text()
            old_passwd = old_pass_widget.get_text()
            new_passwd = new_pass_widget.get_text()
            new_passwd2 = new_pass2_widget.get_text()
            if new_passwd != new_passwd2:
                common.warning(_("Confirmation password do not match " \
                        "new password, operation cancelled!"), win,
                        _("Validation Error."))
            else:
                try:
                    rpc.db_exec(host, port, 'change_admin_password',
                            old_passwd, new_passwd)
                except Exception, exception:
                    rpc.logout()
                    common.warning(_('Change Admin password failed with ' \
                            'error message:\n') + str(exception[0]),
                            self.window, _('Change Admin password failed!'))
                self.refresh_ssl()
        else:
            rpc.logout()
            Main.get_main().refresh_ssl()
        self.window.present()
        win.destroy()

    def sig_db_dump(self, widget):
        url, dbname, passwd = self._choose_db_select(_('Backup a database'))
        if not dbname:
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        host, port = url.rsplit(':', 1)
        try:
            dump_b64 = rpc.db_exec(host, int(port), 'dump', passwd, dbname)
        except Exception, exception:
            rpc.logout()
            Main.get_main().refresh_ssl()
            common.warning(_('Database dump failed with error message:\n') + \
                    str(exception[0]), self.window, _('Database dump failed!'))
            return
        self.refresh_ssl()
        dump = base64.decodestring(dump_b64)

        filename = common.file_selection(_('Save As...'),
                action=gtk.FILE_CHOOSER_ACTION_SAVE, parent=self.window,
                preview=False)

        if filename:
            file_ = file(filename, 'wb')
            file_.write(dump)
            file_.close()
            common.message(_("Database backuped successfully!"),
                    parent=self.window)
        else:
            rpc.logout()
            Main.get_main().refresh_ssl()

    def _choose_db_select(self, title=_("Backup a database")):
        def refreshlist(widget, db_widget, label, host, port):
            res = common.refresh_dblist(db_widget, host, port)
            if res is None or res == -1:
                if res is None:
                    label.set_label('<b>' + _('Could not connect to server!') +\
                            '</b>')
                else:
                    label.set_label('<b>' + \
                            _('Incompatible version of the server!') + '</b>')
                db_widget.hide()
                label.show()
            elif res == 0:
                label.set_label('<b>' + \
                        _('No database found, you must create one!') + '</b>')
                db_widget.hide()
                label.show()
            else:
                label.hide()
                db_widget.show()
            return res

        def refreshlist_ask(widget, server_widget, db_widget, label,
                parent=None):
            res = common.request_server(server_widget, parent)
            if not res:
                return None
            host, port = res
            refreshlist(widget, db_widget, label, host, port)
            return (host, port)

        dialog = glade.XML(GLADE, "win_db_select",
                gettext.textdomain())
        win = dialog.get_widget('win_db_select')
        win.set_icon(TRYTON_ICON)
        win.set_default_response(gtk.RESPONSE_OK)
        win.set_transient_for(self.window)
        win.show_all()

        pass_widget = dialog.get_widget('ent_passwd_select')
        server_widget = dialog.get_widget('ent_server_select')
        db_widget = dialog.get_widget('combo_db_select')
        label = dialog.get_widget('label_db_select')


        dialog.get_widget('db_select_label').set_markup('<b>'+title+'</b>')

        host = CONFIG['login.server']
        port = int(CONFIG['login.port'])
        url = '%s:%d' % (host, port)
        server_widget.set_text(url)

        liststore = gtk.ListStore(str)
        db_widget.set_model(liststore)

        refreshlist(None, db_widget, label, host, port)
        change_button = dialog.get_widget('but_server_select')
        change_button.connect_after('clicked', refreshlist_ask,
                server_widget, db_widget, label, win)

        cell = gtk.CellRendererText()
        db_widget.pack_start(cell, True)
        db_widget.add_attribute(cell, 'text', 0)

        res = win.run()

        database = False
        url = False
        passwd = False
        if res == gtk.RESPONSE_OK:
            database = db_widget.get_active_text()
            url = server_widget.get_text()
            passwd = pass_widget.get_text()
        self.window.present()
        win.destroy()
        return (url, database, passwd)

    def _choose_db_ent(self):
        dialog = glade.XML(GLADE, "win_db_ent",
                gettext.textdomain())
        win = dialog.get_widget('win_db_ent')
        win.set_icon(TRYTON_ICON)
        win.set_transient_for(self.window)
        win.show_all()

        db_widget = dialog.get_widget('ent_db')
        widget_pass = dialog.get_widget('ent_password')
        widget_url = dialog.get_widget('ent_server')

        url = '%s:%d' % (CONFIG['login.server'], int(CONFIG['login.port']))
        widget_url.set_text(url)

        change_button = dialog.get_widget('but_server_change')
        change_button.connect_after('clicked',
                lambda a, b: common.request_server(b, win), widget_url)

        res = win.run()

        database = False
        passwd = False
        url = False
        if res == gtk.RESPONSE_OK:
            database = db_widget.get_text()
            url = widget_url.get_text()
            passwd = widget_pass.get_text()
        self.window.present()
        win.destroy()
        return url, database, passwd

