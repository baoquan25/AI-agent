from daytona import Daytona

daytona = Daytona()
sandbox = daytona.find_one("16495274-4d84-4a94-becb-bd47fabea0e3")

preview = sandbox.get_preview_link(4000)
print(preview.url)
print(preview.token)