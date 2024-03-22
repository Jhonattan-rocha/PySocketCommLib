import random
import re
import string
import uuid

# regex = re.compile(r'\{([^}]*)\}\:\{([^}]*)\}', re.I)
regex = re.compile(r'\!\{(.*?)\}\:\{(.*?)\}\!', re.I)

texto = "poaojdopajoadsdpads!{message}:{texto para ser enviado, False}açskdaskdaksdklç~kads!{message2}:{texto para ser enviado, False}"

print(regex.findall(texto))

def generate_random_str(lng: int) -> str:
    chars = string.ascii_letters + string.ascii_lowercase + string.ascii_uppercase + string.digits + string.hexdigits + string.printable
    return ''.join([random.choice(chars) for _ in range(lng)])


print(uuid.uuid4())
