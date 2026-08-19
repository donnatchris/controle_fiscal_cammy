import time
import uno

from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


local_ctx = uno.getComponentContext()

resolver = local_ctx.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver",
    local_ctx,
)

ctx = None

for _ in range(20):
    try:
        ctx = resolver.resolve(
            "uno:socket,host=localhost,port=2002;"
            "urp;StarOffice.ComponentContext"
        )
        break
    except Exception:
        time.sleep(0.5)

if ctx is None:
    raise RuntimeError("Impossible de se connecter à LibreOffice")

smgr = ctx.ServiceManager

desktop = smgr.createInstanceWithContext(
    "com.sun.star.frame.Desktop",
    ctx,
)

doc = desktop.loadComponentFromURL(
    "private:factory/scalc",
    "_blank",
    0,
    (),
)

sheet = doc.Sheets.getByIndex(0)

sheet.getCellRangeByName("A1").String = "UNO fonctionne dans Docker"
sheet.getCellRangeByName("A2").Value = 123.45

url = uno.systemPathToFileUrl("/data/test_uno.ods")

doc.storeAsURL(
    url,
    (
        prop("FilterName", "calc8"),
    ),
)

doc.close(True)

print("ODS créé : /data/test_uno.ods")