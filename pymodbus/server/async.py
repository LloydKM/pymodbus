'''
Implementation of a Twisted Modbus Server
------------------------------------------

Example run::

    context = ModbusServerContext(d=[0,100], c=[0,100], h=[0,100], i=[0,100])
    reactor.listenTCP(502, ModbusServerFactory(context))
    reactor.run()
'''
from binascii import b2a_hex
from twisted.internet.protocol import Protocol, ServerFactory

from pymodbus.constants import Defaults
from pymodbus.factory import ServerDecoder
from pymodbus.datastore import ModbusServerContext
from pymodbus.device import ModbusControlBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.transaction import ModbusSocketFramer, ModbusAsciiFramer
from pymodbus.interfaces import IModbusFramer
from pymodbus.mexceptions import *
from pymodbus.pdu import ModbusExceptions as merror

#---------------------------------------------------------------------------#
# Logging
#---------------------------------------------------------------------------#
import logging
_logger = logging.getLogger("pymodbus.server")

#---------------------------------------------------------------------------#
# Server
#---------------------------------------------------------------------------#
class ModbusProtocol(Protocol):
    ''' Implements a modbus server in twisted '''

    def connectionMade(self):
        ''' Callback for when a client connects
       
        Note, since the protocol factory cannot be accessed from the
        protocol __init__, the client connection made is essentially our
        __init__ method.     
        '''
        #_logger.debug("Client Connected [%s]" % self.transport.getHost())
        _logger.debug("Client Connected [%s]" % self.transport)
        self.framer = self.factory.framer(decoder=self.factory.decoder)

    def connectionLost(self, reason):
        '''
        Callback for when a client disconnects
        @param reason The client's reason for disconnecting
        '''
        _logger.debug("Client Disconnected")

    def dataReceived(self, data):
        '''
        Callback when we receive any data
        @param data The data sent by the client
        '''
        _logger.debug(" ".join([hex(ord(x)) for x in data]))
        # if not self.factory.control.ListenOnly:
        self.framer.processIncomingPacket(data, self.execute)

#---------------------------------------------------------------------------#
# Extra Helper Functions
#---------------------------------------------------------------------------#
    def execute(self, request):
        '''
        Executes the request and returns the result
        @param request The decoded request message
        '''
        try:
            context = self.factory.store[request.unit_id]
            response = request.execute(context)
        except Exception, ex:
            _logger.debug("Datastore unable to fulfill request %s" % ex)
            response = request.doException(merror.SlaveFailure)
        #self.framer.populateResult(response)
        response.transaction_id = request.transaction_id
        response.unit_id = request.unit_id
        self.send(response)

    def send(self, message):
        '''
        Send a request (string) to the network
        @param message The unencoded modbus response
        '''
        #self.factory.control.Counter.BusMessage += 1
        pdu = self.framer.buildPacket(message)
        _logger.debug('send: %s' % b2a_hex(pdu))
        return self.transport.write(pdu)


class ModbusServerFactory(ServerFactory):
    '''
    Builder class for a modbus server

    This also holds the server datastore so that it is
    persisted between connections
    '''

    protocol = ModbusProtocol

    def __init__(self, store, framer=None, identity=None):
        ''' Overloaded initializer for the modbus factory

        If the identify structure is not passed in, the ModbusControlBlock
        uses its own empty structure.

        :param store: The ModbusServerContext datastore
        :param framer: The framer strategy to use
        :param identity: An optional identify structure

        '''
        self.decoder = ServerDecoder()
        self.framer = framer or ModbusSocketFramer
        self.store = store or ModbusServerContext()
        self.control = ModbusControlBlock()

        if isinstance(identity, ModbusDeviceIdentification):
            self.control.Identity.update(identity)

#---------------------------------------------------------------------------# 
# Starting Factories
#---------------------------------------------------------------------------# 
def StartTcpServer(context, identity=None):
    ''' Helper method to start the Modbus Async TCP server
    :param context: The server data context
    :param identify: The server identity to use (default empty)
    '''
    from twisted.internet import reactor

    _logger.info("Starting Modbus TCP Server on %s" % Defaults.Port)
    framer = ModbusSocketFramer
    factory = ModbusServerFactory(store=context, framer=framer, identity=identity)
    reactor.listenTCP(Defaults.Port, factory)
    reactor.run()

def StartUdpServer(context, identity=None):
    ''' Helper method to start the Modbus Async Udp server
    :param context: The server data context
    :param identify: The server identity to use (default empty)
    '''
    from twisted.internet import reactor

    _logger.info("Starting Modbus UDP Server on %s" % Defaults.Port)
    framer = ModbusSocketFramer
    factory = ModbusServerFactory(store=context, framer=framer, identity=identity)
    reactor.listenUDP(Defaults.Port, factory)
    reactor.run()

def StartSerialServer(context, identity=None, framer=ModbusAsciiFramer, **kwargs):
    ''' Helper method to start the Modbus Async Serial server
    :param context: The server data context
    :param identify: The server identity to use (default empty)
    :param framer: The framer to use (default ModbusAsciiFramer)
    '''
    from twisted.internet import reactor
    from twisted.internet.serialport import SerialPort

    _logger.info("Starting Modbus Serial Server on %s" % kwargs['device'])
    factory = ModbusServerFactory(store=context, framer=framer, identity=identity)
    protocol = factory.buildProtocol(None)
    handle = SerialPort(protocol, kwargs['device'], reactor, Defaults.Baudrate)
    reactor.run()

#---------------------------------------------------------------------------# 
# Helper Methods
#---------------------------------------------------------------------------# 
def install_specialized_reactor():
    '''
    This attempts to install a reactor specialized for the given
    operating system.

    :returns: True if a specialized reactor was installed, False otherwise
    '''
    from twisted.internet import epollreactor, kqreactor, iocpreactor
    for reactor in [epollreactor, kqreactor, iocpreactor]:
        try:
            reactor.install()
            _logger.debug("Installed %s" % reactor.__name__)
            return True
        except: pass
    _logger.debug("No specialized reactor was installed")
    return False

#---------------------------------------------------------------------------# 
# Exported symbols
#---------------------------------------------------------------------------# 
__all__ = [
    "StartTcpServer", "StartUdpServer",
    "install_specialized_reactor",
]