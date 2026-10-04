import json

from common import image_ref, output, run


def inspect(image):
    image_ref(image)
    run(["docker", "pull", image], timeout=600)
    script = """
import importlib.metadata,json,os,subprocess
release=dict(line.strip().split('=',1) for line in open('/etc/os-release') if '=' in line)
print(json.dumps({'postgres':subprocess.check_output(['postgres','--version'],text=True).split()[2],
 'patroni':importlib.metadata.version('patroni'),'uid':os.getuid(),
 'os':release['ID']+':'+release['VERSION_ID']}))
"""
    return json.loads(output(["docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
                              "--security-opt=no-new-privileges", "--entrypoint=/opt/patroni/bin/python",
                              image, "-c", script]))
