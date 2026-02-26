from daytona import Daytona

daytona = Daytona()
sandbox = daytona.find_one("387db1c5-80b9-4f2a-8883-c82fa6ef2258")

preview = sandbox.get_preview_link(3800)
print(preview.url)
print(preview.token)