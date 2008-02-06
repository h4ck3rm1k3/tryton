import common
import os
import imp

PLUGINS_PATH = os.path.join(os.path.dirname(__file__), 'plugins')

def execute(datas, parent):
    result = {}

    for plugin in os.listdir(PLUGINS_PATH):
        module = os.path.splitext(plugin)[0]
        try:
            module = imp.load_module(module, *imp.find_module(module, [PLUGINS_PATH]))
            for name, func in module.get_plugins(datas['model']):
                result[name] = func
        except Exception, exception:
            print exception
            continue
    if not result:
        common.message(_('No available plugin for this resource!'), parent)
        return False
    res = common.selection(_('Choose a Plugin'), result, parent, alwaysask=True)
    if res:
        res[1](datas, parent)
    return True
