import asyncio
from asyncua import Client, ua
import time

class PLCConnector:
    def __init__(self, endpoint="opc.tcp://localhost:4840"):
        self.endpoint = endpoint
        self.client = Client(self.endpoint)
        self.is_connected = False

    async def connect(self):
        try:
            await self.client.connect()
            self.is_connected = True
            print(f"AntiÑapas-Pons: Conectado al PLC en {self.endpoint}")
            return True
        except Exception as e:
            print(f"Error de conexión PLC: {e}")
            return False

    async def send_emergency_stop(self):
        """Dispara el bit de emergencia en el PLC"""
        if not self.is_connected: return
        try:
            # Ejemplo: Escribir en una variable del PLC
            # node = self.client.get_node("ns=2;i=2") 
            # await node.write_value(True)
            print("!!! EMERGENCY STOP SENT TO PLC !!!")
        except Exception as e:
            print(f"Error enviando emergencia: {e}")

    async def send_heartbeat(self):
        """Envía un bit que alterna cada segundo para el Watchdog del PLC"""
        val = False
        while self.is_connected:
            try:
                # node = self.client.get_node("ns=2;i=3")
                # await node.write_value(val)
                val = not val
                await asyncio.sleep(1)
            except:
                self.is_connected = False
                break

    async def get_machine_mode(self):
        """Lee el modo actual de la máquina desde el PLC"""
        if not self.is_connected: return "MANUAL"
        try:
            # node = self.client.get_node("ns=2;i=4")
            # val = await node.read_value()
            # return val (un string o int mapeado)
            return "AUTOMATICO"
        except:
            return "UNKNOWN"

    async def disconnect(self):
        await self.client.disconnect()
        self.is_connected = False

if __name__ == "__main__":
    # Test rápido de conexión
    conn = PLCConnector()
    asyncio.run(conn.connect())
