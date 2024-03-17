import asyncio
from concurrent.futures import ThreadPoolExecutor
import re
import threading
from typing import Any, Callable

class Events:
    
    def __init__(self) -> None:
        self.__events = {}
                
    # !{flag}:{arg, arg, arg}!
    def scam(self, data: bytes):
        texto = data.decode()
        regex = re.compile(r'\!\{([^}]*)\}\:\{([^}]*)\}\!', re.I)
        events = regex.findall(texto)
        
        for event in events:
            flag = str(event[0])
            args = str(event[1]).split(",")
            threading.Thread(target=self.__events[flag], args=tuple(args)).start()
    
    def size(self):
        return len(self.__events)
                
    def on(self, flag: str, call: Callable[..., Any]):
        self.__events[flag] = call
    
    async def async_executor(self, Call: Callable[..., Any], *args):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            res = await loop.run_in_executor(executor, Call, *args)
        return res
