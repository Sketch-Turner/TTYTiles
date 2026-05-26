from ttytiles import FDInterceptor
import os
import sys

# install
stdout_hook = FDInterceptor(1)
stderr_hook = FDInterceptor(2)

print("hidden")
print("IMPORTANT visible")

os.system("echo IMPORTANT subprocess")
os.system("echo hidden subprocess")

sys.stderr.write("IMPORTANT stderr\n")
sys.stderr.write("stderr\n")
sys.stderr.flush()

# clean shutdown
stdout_hook.close()
stderr_hook.close()