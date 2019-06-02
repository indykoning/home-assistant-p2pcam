import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_HOST, CONF_IP_ADDRESS
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_HORIZONTAL_FLIP = 'horizontal_flip'
CONF_VERTICAL_FLIP = 'vertical_flip'
CONF_TIMESTAMP = 'timestamp'

DEFAULT_NAME = 'p2pcam'
DEFAULT_HORIZONTAL_FLIP = 0
DEFAULT_VERTICAL_FLIP = 0
DEFAULT_TIMESTAMP = 0

REQUIREMENTS = ['opencv-python==4.0.0.21']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_IP_ADDRESS): cv.string,
    vol.Optional(CONF_HORIZONTAL_FLIP, default=DEFAULT_HORIZONTAL_FLIP):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
    vol.Optional(CONF_VERTICAL_FLIP, default=DEFAULT_VERTICAL_FLIP):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
    vol.Optional(CONF_TIMESTAMP, default=DEFAULT_TIMESTAMP):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    async_add_entities([P2PCam(hass, config)])


class P2PCam(Camera):
    def __init__(self, hass, config):
        super().__init__()

        self._name = config.get(CONF_NAME)
        self._host_ip = config.get(CONF_HOST)
        self._target_ip = config.get(CONF_IP_ADDRESS)

        self.camera = P2PCam_req(self._host_ip, self._target_ip)
        self.camera.horizontal_flip = (bool(config.get(CONF_HORIZONTAL_FLIP)) == 1)
        self.camera.vertical_flip = (int(config.get(CONF_VERTICAL_FLIP)) == 1)
        self.camera.vertical_flip = (int(config.get(CONF_VERTICAL_FLIP)) == 1)
        self.camera.addTimeStamp = (int(config.get(CONF_TIMESTAMP)) == 1)

    async def async_camera_image(self):
        return self.camera.retrieveImage()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

import sys, traceback
import socket
import time
import random

class RestartException(Exception):
    def __init__(self, msg, delay=1):
        self.msg = msg
        self.delay = delay

    def __str__(self):
        return repr(self.msg)


class P2PCam_req():
    def __init__(self, host_ip, target_ip):
        self.horizontal_flip = False
        self.vertical_flip = False
        self.addTimeStamp = False

        self.global_loop_iteration = 0
        # Our IP address
        self.UDP_IP_HOST = host_ip
        self.UDP_PORT_HOST = 5123  # arbitrary
        # Camera IP address and UDP port
        self.UDP_IP_TARGET = target_ip
        self.UDP_PORT_TARGET = 5000
        # network socket timeout in seconds
        self.SOCKET_TIMEOUT = 2
        # Nb of UDP packets to receive to get one full image.
        # Packets are typically 904 bytes, 80 packets is about 70kB, which is enough
        # for the camera setup I used (640x480 medium quality jpeg)
        self.NB_FRAGMENTS_TO_ACCUMULATE = 80
        self.jpeg = None
        self.MESSAGE_43 = bytearray(
            [0x00, 0x00, 0xb0, 0x02, 0x82, 0x00, 0x00, 0x27, 0x00, 0x01, 0x00, 0x00, 0x00, 0x4d, 0x61, 0x63, 0x49, 0x50,
             0x3d, 0x42, 0x43, 0x2d, 0x41, 0x45, 0x2d, 0x43, 0x35, 0x2d, 0x37, 0x43, 0x2d, 0x37, 0x37, 0x2d, 0x37, 0x42,
             0x2b, 0x31, 0x36, 0x34, 0x36, 0x37, 0x3b])
        self.MESSAGE_13_1 = bytearray([0x00, 0x00, 0xd0, 0x00, 0x82, 0x00, 0x06, 0x09, 0x00, 0x01, 0x00, 0x00, 0x00])
        self.MESSAGE_13_2 = bytearray([0x00, 0x00, 0xd0, 0x00, 0xa2, 0x00, 0x06, 0x09, 0x00, 0x01, 0x00, 0x00, 0x00])
        self.MESSAGE_13_3 = bytearray([0x00, 0x00, 0xd0, 0x00, 0x62, 0x00, 0x06, 0x09, 0x00, 0x01, 0x00, 0x00, 0x00])
        self.MESSAGE_212 = bytearray(
            [0x01, 0x00, 0x40, 0x0d, 0x32, 0x00, 0x00, 0xd0, 0x00, 0x51, 0x01, 0x00, 0x00, 0x69, 0x64, 0xd4, 0xd8, 0xd8,
             0xd2, 0x8f, 0x9d, 0xa7, 0xd9, 0xd4, 0x9f, 0x80, 0x8d, 0x8c, 0x86, 0xc7, 0x9f, 0x8b, 0xbf, 0x80, 0x8d, 0x8c,
             0x86, 0xc7, 0xa4, 0xb9, 0xac, 0xae, 0xdd, 0xd2, 0x8f, 0x9d, 0xa7, 0xd8, 0xd4, 0x87, 0x8c, 0x9d, 0xc7, 0xd9,
             0xd2, 0x8f, 0x9d, 0xa7, 0xdb, 0xd4, 0xa1, 0xa2, 0xb9, 0xaa, 0xb9, 0x9b, 0x8c, 0x9a, 0x8c, 0x87, 0x9d, 0xc7,
             0xa1, 0xa2, 0xb9, 0xaa, 0xb9, 0x9b, 0x8c, 0x9a, 0x8c, 0x87, 0x9d, 0xd2, 0x86, 0x99, 0xa7, 0xdb, 0xd4, 0xdc,
             0x98, 0x8d, 0xdf, 0xa6, 0xa3, 0xdf, 0xda, 0xda, 0xdf, 0xde, 0x8f, 0x8f, 0x8f, 0xd2, 0xaa, 0x88, 0x85, 0x85,
             0x80, 0x8d, 0xd4, 0xdd, 0x85, 0x90, 0xd9, 0x81, 0x8f, 0xdc, 0x82, 0xd8, 0xde, 0xa8, 0xd9, 0xd9, 0xae, 0xb3,
             0xd8, 0xd0, 0x8f, 0xda, 0x85, 0xdc, 0xde, 0xad, 0x8a, 0xdf, 0xda, 0xda, 0xdf, 0xd9, 0x8f, 0x8f, 0xd9, 0xd2,
             0x9a, 0x80, 0x8d, 0xa7, 0xd4, 0xdc, 0x98, 0x8d, 0xdf, 0xa6, 0xa3, 0xdf, 0xda, 0xda, 0xdf, 0xde, 0x8f, 0x8f,
             0x8f, 0xd2, 0xa8, 0x9a, 0xaa, 0x86, 0x8d, 0x8c, 0xd4, 0xda, 0xda, 0xde, 0xd2, 0xa4, 0x88, 0x80, 0x87, 0xaa,
             0x84, 0x8d, 0xd4, 0xa1, 0xa2, 0xb6, 0xbb, 0xac, 0xba, 0xb6, 0xbb, 0xac, 0xb8, 0xd2, 0x9c, 0x9a, 0x8c, 0x9b,
             0xd4, 0xd8, 0xd0, 0xdb, 0xc7, 0xd8, 0xdf, 0xd1, 0xc7, 0xd9, 0xc7, 0xda, 0xda, 0xd2])
        self.MESSAGE_34 = bytearray(
            [0x00, 0x00, 0x20, 0x02, 0x12, 0x00, 0x00, 0x1e, 0x00, 0x01, 0x00, 0x00, 0x00, 0xa0, 0xaa, 0xa4, 0xad, 0xd4,
             0xd8, 0xd2, 0xba, 0xac, 0xb8, 0xd4, 0xd8, 0xd2, 0xbd, 0xa0, 0xa4, 0xac, 0xd4, 0xd9, 0xd2, 0xe9])
        self.MESSAGE_119 = bytearray(
            [0x02, 0x00, 0x70, 0x07, 0x32, 0x00, 0x00, 0x73, 0x00, 0x64, 0x00, 0x00, 0x00, 0x4d, 0x61, 0x80, 0x87, 0xaa,
             0x84, 0x8d, 0xd4, 0xba, 0x8c, 0x9a, 0x9a, 0x80, 0x86, 0x87, 0xba, 0x9d, 0x88, 0x9b, 0x9d, 0xd2, 0x9a, 0x80,
             0x8d, 0xa7, 0xd4, 0xdc, 0x98, 0x8d, 0xdf, 0xa6, 0xa3, 0xdf, 0xda, 0xda, 0xdf, 0xde, 0x8f, 0x8f, 0x8f, 0xd2,
             0x8f, 0x9d, 0xa7, 0xd9, 0xd4, 0xa1, 0xa2, 0xb9, 0xaa, 0xb9, 0x9b, 0x8c, 0x9a, 0x8c, 0x87, 0x9d, 0xc7, 0xa1,
             0xa2, 0xb9, 0xaa, 0xb9, 0x9b, 0x8c, 0x9a, 0x8c, 0x87, 0x9d, 0xd2, 0xaf, 0xad, 0xd9, 0xd4, 0xdb, 0xdc, 0xd8,
             0xdd, 0xd0, 0xdb, 0xd1, 0xd1, 0xd2, 0x8f, 0x9d, 0xa7, 0xd8, 0xd4, 0x87, 0x8c, 0x9d, 0xc7, 0xd8, 0xd9, 0xdb,
             0xdc, 0xd2, 0xaf, 0xad, 0xd8, 0xd4, 0xd8, 0xd9, 0xdb, 0xdc, 0xd2])
        # Allowed byte length received after MESSAGE_119, since not all cameras send the same byte length in return.
        self.allowedPacketLengths = [368, 334]
        # The continue packet is composed of a first part where the 0xff below get dynamically replaced by the appropriate value at runtime, and a second part that is invariable
        self.MESSAGE_CONTINUE_BEGIN = bytearray(
            [0x00, 0x00, 0xff, 0x02, 0x12, 0x00, 0x00, 0xff, 0x00, 0x01, 0x00, 0x00, 0x00, 0xa0, 0xaa, 0xa4, 0xad, 0xd4,
             0xd8, 0xd2, 0xba, 0xac, 0xb8, 0xd4])
        self.MESSAGE_CONTINUE_END = bytearray([0xd2, 0xbd, 0xa0, 0xa4, 0xac, 0xd4, 0xd9, 0xd2, 0xe9])
        # in the continue packet, each digit goes through this sequence
        self.CONTINUE_LIST_2 = bytearray([0xd9, 0xd8, 0xdb, 0xda, 0xdd, 0xdc, 0xdf, 0xde, 0xd1, 0xd0])
        # in the continue packet, the last digit toggles between two values (e.g. 0xd8 and 0xdf)
        # periodically, change the toggle set (e.g move to 0xdb/0xde)
        self.CONTINUE_LIST_1 = bytearray(
            [0xd8, 0xdf, 0xdb, 0xde, 0xda, 0xd1, 0xdd, 0xd0, 0xdc, 0xd9, 0xdf, 0xd8, 0xde, 0xdb, 0xd1, 0xda, 0xd0, 0xdd,
             0xd9, 0xdc])
        self.sock = None
        self.onJpegReceived = None
        self.latestErrorMsg = None
        # buffer for control/initialization packets reception
        self.buffer = bytearray(1024)
        self.global_loop_iteration = 0
        self.msg = bytearray()
        self.timeout_iteration = 0
        self.hasInitialised = False

    def byteToInt(self, byteVal):
        return byteVal

    def sendControlPacket(self, packet):
        print(("[CONTROL] sending %d bytes " % len(packet)))
        self.sock.sendto(packet, (self.UDP_IP_TARGET, self.UDP_PORT_TARGET))

    def sendContinuePacket(self, packet):
        self.sock.sendto(packet, (self.UDP_IP_TARGET, self.UDP_PORT_TARGET))

    def receiveControlPacket(self, output):
        self.sock.settimeout(self.SOCKET_TIMEOUT)
        try:
            nbbytes, addr = self.sock.recvfrom_into(output, 1024)
            print(("[CONTROL] received %d bytes " % nbbytes))
            return nbbytes
        except socket.timeout:
            raise socket.timeout
        except KeyboardInterrupt:
            raise

    def start(self):
        try:
            # self.initialize()
            while True:
                self.loop()
        except KeyboardInterrupt:
            print(("[CONTROL] manually interrupted, %s" % time.strftime("%Y-%m-%d @ %H:%M:%S")))
        except NameError as n:
            print(("[ERROR] NameError %s" % n))
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
            del exc_traceback
        print("[CONTROL] exiting surveillance")

    def initialize(self):
        try:
            if self.horizontal_flip and self.vertical_flip:
                self.flipcode = -1
            elif self.horizontal_flip:
                self.flipcode = 0
            elif self.vertical_flip:
                self.flipcode = 1
            self.global_loop_iteration += 1
            print("*****************************************************************")
            print(("Global loop iteration #%d started on %s" % (
                self.global_loop_iteration, time.strftime("%Y-%m-%d @ %H:%M:%S"))))
            print("*****************************************************************")
            #########################
            # VARIOUS INITIALIZATIONS
            #########################
            # the 7th byte in the 13 byte msg seems to be arbitrary: pick any random value for which bit 4 is not already set
            val = random.randint(0, 16)
            self.MESSAGE_13_1[6] = val
            self.MESSAGE_13_2[6] = val
            self.MESSAGE_13_3[6] = val
            self.msg = b''
            self.imageIndex = 0
            self.lastFragmentId = 0
            self.fragmentIndex = 0
            self.nbDigits = 1
            self.continue_index = [0, 0, 0, 0, 0]
            self.base_index = 0
            self.fragments_received = 0
            self.bytes = ''
            self.socket_error = False
            #######################
            # NETWORK RELATED SETUP
            #######################
            # In case this is not the first run
            if self.sock:
                self.sock.close()
            # Open UDP socket to talk to camera
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.bind((self.UDP_IP_HOST, self.UDP_PORT_HOST))
            except socket.error as e:
                if self.sock:
                    self.sock.close()
                self.latestErrorMsg = e.strerror
                raise RestartException("Could not open socket: " + e.strerror, 15)
            except KeyboardInterrupt:
                raise
            ################################
            # CAMERA INITIALIZATION SEQUENCE
            ################################
            self.sendControlPacket(self.MESSAGE_43)
            self.sendControlPacket(self.MESSAGE_13_1)

            for i in range(5):
                try:
                    nbReceived = self.receiveControlPacket(self.buffer)
                    if ((nbReceived == 13) and (self.buffer[4] == (self.MESSAGE_13_1[4] | 0b00010000)) and (
                            self.buffer[6] != (self.MESSAGE_13_1[6] | 0b01000000))):
                        print("[CONTROL] status ok")
                        break
                    else:
                        print("[CONTROL] status ko, repeating")
                        # print("status ko: repeat (buff4=%x, mess4and=%x)" % (self.buffer[4],(MESSAGE_13_1[4] | 0b00010000)))
                        if (i == 9):
                            raise RestartException("Max number of status check loops reached", 15)
                except socket.timeout:
                    if self.timeout_iteration > 3:
                        raise Exception('Not responding')
                    self.timeout_iteration +=1
                    raise RestartException("Socket timeout 1", 1)
                except KeyboardInterrupt:
                    raise
            self.sendControlPacket(self.MESSAGE_13_2)
            self.sendControlPacket(self.MESSAGE_13_3)
            try:
                nbReceived = self.receiveControlPacket(self.buffer)
                if (nbReceived != 13):
                    raise RestartException("Expected 13 bytes, received %d" % nbReceived, 5)
            except socket.timeout:
                raise RestartException("Socket timeout 2", 15)
            except KeyboardInterrupt:
                raise
            self.sendControlPacket(self.MESSAGE_212)
            try:
                nbReceived = self.receiveControlPacket(self.buffer)
                # Sometimes the 42 bytes packet comes before the 115: discard it and re-read
                if (nbReceived == 42):
                    print("[CONTROL] received 42 early, re-reading")
                    nbReceived = self.receiveControlPacket(self.buffer)
                if (nbReceived != 155 and nbReceived != 156):
                    raise RestartException("Expected 155 bytes, received %d" % nbReceived, 15)
            except socket.timeout:
                raise RestartException("Socket timeout 3", 15)
            except KeyboardInterrupt:
                raise
            self.sendControlPacket(self.MESSAGE_34)
            self.sendControlPacket(self.MESSAGE_119)
            try:
                nbReceived = self.receiveControlPacket(self.buffer)
                # Sometimes the 42 bytes packet comes at this point: discard it and re-read
                if (nbReceived == 42):
                    print("[CONTROL] received 42 late, re-reading")
                    nbReceived = self.receiveControlPacket(self.buffer)
                if (nbReceived not in self.allowedPacketLengths):
                    raise RestartException(
                        "Expected one of %(allowedPacketLengths)s bytes, received %(receivedBytes)d" % {
                            "allowedPacketLengths": self.allowedPacketLengths, "receivedBytes": nbReceived}, 15)
            except socket.timeout:
                raise RestartException("Socket timeout 4", 15)
            except KeyboardInterrupt:
                raise
            # reception packet TAPA 410 & paquet 42 bytes
            # receiveControlPacket(self.buffer)
        except RestartException as resExc:
            print(("[ERROR] restarting global loop in %d seconds due to exception: %s" % (resExc.delay, resExc.msg)))
            # Let the camera breathe a bit before trying again
            time.sleep(resExc.delay)
            self.initialize()
            pass
        except KeyboardInterrupt:
            raise


    def retrieveImage(self):
        if not self.hasInitialised:
            self.initialize()
            self.hasInitialised = True
        try:
            ############################
            # BEGIN IMAGE RECEPTION LOOP
            ############################
            foundImage = False

            while self.socket_error == False and foundImage == False:
                self.sock.settimeout(self.SOCKET_TIMEOUT)
                # Receive UDP fragment
                try:
                    chunk = self.sock.recv(1024)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.socket_error = True
                    print("[DATA] self.sock.recv error: " + str(e))
                    self.initialize()
                    return self.retrieveImage()

                nbbytes = len(chunk)
                self.fragments_received += 1
                self.fragmentIndex += 1
                if (self.fragments_received <= self.NB_FRAGMENTS_TO_ACCUMULATE):
                    # Filter out any potential non-image-data packets (e.g. 13 bytes statuses)
                    if nbbytes >= 17:
                        # First frame / Start of Image : get rid of the 15 bytes header
                        if (chunk[15] == 255) and (chunk[16] == 216):
                            self.lastFragmentId = self.byteToInt(chunk[0])
                            self.msg += chunk[15:]
                        # additional data fragment : just drop the 4 bytes header and concatenate to already received data
                        else:
                            # Check for sequence number continuity
                            if ((self.byteToInt(chunk[0]) == self.lastFragmentId + 1) or (
                                    self.byteToInt(chunk[0]) == 0) and (self.lastFragmentId == 255)):
                                self.msg += chunk[4:]
                            # If we lost a fragment, no point in continuing accumulating data for this frame so restart another data grab
                            else:
                                self.msg = b''
                                self.fragments_received = 0
                            # Keep track of sequence number
                            self.lastFragmentId = self.byteToInt(chunk[0])
                    # If we received an unexpected packet in the middle of the image data, something is wrong : just drop the ongoing image capture & restart
                    else:
                        self.msg = b''
                        self.fragments_received = 0
                    self.manageContinuePackets()
                else:
                    # We now normally have enough data so that a full image is present in the buffer: search for SOI and EOI markers
                    # SOI = 0xffd8
                    # EOI = 0xffd9
                    SOI_index = -1
                    EOI_index = -1
                    for index in range(0, len(self.msg) - 1):
                        if (self.msg[index] == 255):
                            if self.msg[index + 1] == 216:
                                SOI_index = index
                                for index in range(index + 2, len(self.msg) - 1):
                                    if (self.msg[index] == 255):
                                        if self.msg[index + 1] == 217:
                                            EOI_index = index
                                            break
                                break
                    if SOI_index != -1 and EOI_index != -1:
                        # A complete image was indeed found in the data buffer : isolate the image data in a dedicated buffer
                        # Keep the rest of data for next iterations
                        self.jpeg = self.msg[SOI_index:EOI_index + 2]
                        self.msg = self.msg[EOI_index + 2:]
                        try:
                            foundImage = True
                            if callable(self.onJpegReceived):
                                self.onJpegReceived(self, self.jpeg)
                        except KeyboardInterrupt:
                            raise
                        except:
                            exc_type, exc_value, exc_traceback = sys.exc_info()
                            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
                            del exc_traceback
                            pass
                        # Log a trace every 5 min or so (5*60s*3img/sec)
                        if (self.imageIndex % 900 == 0):
                            print(("[DATA] Still alive %s, image index %d" % (
                                time.strftime("%Y-%m-%d @ %H:%M:%S"), self.imageIndex)))
                        self.imageIndex += 1
                    #        else:
                    #            print("no image found in stream among %d bytes"% len(self.msg))
                    # Restart another data grab
                    self.msg = b''
                    self.fragments_received = 0
                    self.manageContinuePackets()
                    if hasattr(self, 'flipcode') or self.addTimeStamp:
                        import cv2, numpy
                        image = cv2.imdecode(numpy.fromstring(self.jpeg, dtype=numpy.uint8),cv2.IMREAD_COLOR)
                        if hasattr(self, 'flipcode'):
                            cv2.flip(image, self.flipcode, image)
                        if self.addTimeStamp:
                            cv2.putText(image, time.strftime("%Y-%m-%d  %H:%M:%S"), (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2, 8)
                        return cv2.imencode('.jpg', image)[1].tostring()
                    return self.jpeg
            if self.socket_error:
                self.initialize()
                return self.retrieveImage()
        except RestartException as resExc:
            print(("[ERROR] restarting global loop in %d seconds due to exception: %s" % (resExc.delay, resExc.msg)))
            # Let the camera breathe a bit before trying again
            time.sleep(resExc.delay)
            pass
        except KeyboardInterrupt:
            raise

    def manageContinuePackets(self):
        ####################################
        # MANAGE "CONTINUE" PACKETS SEQUENCE
        ####################################
        # Send out a feedback message every 5 fragments received, to tell the camera to keep sending frames.
        if (self.fragmentIndex % 5) == 0:
            tmp = bytearray()
            if (self.nbDigits == 1):
                self.MESSAGE_CONTINUE_BEGIN[2] = 0x20
                self.MESSAGE_CONTINUE_BEGIN[7] = 0x1e
                tmp.append(self.CONTINUE_LIST_1[self.base_index + self.continue_index[0]])
                self.continue_index[0] += 1
                if self.continue_index[0] == 2:
                    self.nbDigits += 1
                    self.continue_index[1] = 1  # start at d8
                    self.continue_index[0] = 0
            elif (self.nbDigits == 2):
                self.MESSAGE_CONTINUE_BEGIN[2] = 0x30
                self.MESSAGE_CONTINUE_BEGIN[7] = 0x1f
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[1]])
                tmp.append(self.CONTINUE_LIST_1[self.base_index + self.continue_index[0]])
                self.continue_index[0] += 1
                if self.continue_index[0] == 2:
                    self.continue_index[1] += 1
                    self.continue_index[0] = 0
                if self.continue_index[1] == len(self.CONTINUE_LIST_2):
                    self.nbDigits += 1
                    self.continue_index[2] = 1  # start at d8
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0
            elif (self.nbDigits == 3):
                self.MESSAGE_CONTINUE_BEGIN[2] = 0x40
                self.MESSAGE_CONTINUE_BEGIN[7] = 0x20
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[2]])
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[1]])
                tmp.append(self.CONTINUE_LIST_1[self.base_index + self.continue_index[0]])
                # update digit 0
                self.continue_index[0] += 1
                # update digit 1
                if self.continue_index[0] == 2:
                    self.continue_index[1] += 1
                    self.continue_index[0] = 0
                # update digit 2
                if self.continue_index[1] == len(self.CONTINUE_LIST_2):
                    self.continue_index[2] += 1
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0
                # check for adding one more digit
                if self.continue_index[2] == len(self.CONTINUE_LIST_2):
                    self.nbDigits += 1
                    self.continue_index[3] = 1  # start at d8
                    self.continue_index[2] = 0  # start at d9
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0  # start at d9
            elif (self.nbDigits == 4):
                self.MESSAGE_CONTINUE_BEGIN[2] = 0x50
                self.MESSAGE_CONTINUE_BEGIN[7] = 0x21
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[3]])
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[2]])
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[1]])
                tmp.append(self.CONTINUE_LIST_1[self.base_index + self.continue_index[0]])
                # update digit 0
                self.continue_index[0] += 1
                # update digit 1
                if self.continue_index[0] == 2:
                    self.continue_index[1] += 1
                    self.continue_index[0] = 0
                # update digit 2
                if self.continue_index[1] == len(self.CONTINUE_LIST_2):
                    self.continue_index[2] += 1
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0
                # update digit 3
                if self.continue_index[2] == len(self.CONTINUE_LIST_2):
                    self.continue_index[3] += 1  # start at d8
                    self.continue_index[2] = 0  # start at d9
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0  # start at d9
                # check for adding one more digit
                if self.continue_index[3] == len(self.CONTINUE_LIST_2):
                    self.nbDigits += 1
                    self.continue_index[4] = 1  # start at d8
                    self.continue_index[3] = 0  # start at d9
                    self.continue_index[2] = 0  # start at d9
                    self.continue_index[1] = 0  # start at d9
            elif (self.nbDigits == 5):
                self.MESSAGE_CONTINUE_BEGIN[2] = 0x60
                self.MESSAGE_CONTINUE_BEGIN[7] = 0x22
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[4]])
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[3]])
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[2]])
                tmp.append(self.CONTINUE_LIST_2[self.continue_index[1]])
                tmp.append(self.CONTINUE_LIST_1[self.base_index + self.continue_index[0]])
                # update digit 0
                self.continue_index[0] += 1
                # update digit 1
                if self.continue_index[0] == 2:
                    self.continue_index[1] += 1
                    self.continue_index[0] = 0
                # update digit 2
                if self.continue_index[1] == len(self.CONTINUE_LIST_2):
                    self.continue_index[2] += 1
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0
                # update digit 3
                if self.continue_index[2] == len(self.CONTINUE_LIST_2):
                    self.continue_index[3] += 1  # start at d8
                    self.continue_index[2] = 0  # start at d9
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0  # start at d9
                # update digit 4
                if self.continue_index[3] == len(self.CONTINUE_LIST_2):
                    self.continue_index[4] += 1  # start at d8
                    self.continue_index[3] = 0  # start at d9
                    self.continue_index[2] = 0  # start at d9
                    self.continue_index[1] = 0  # start at d9
                    self.continue_index[0] = 0  # start at d9
                if self.continue_index[4] == len(self.CONTINUE_LIST_2):
                    # restart sequence
                    # print("RESTARTING SEQUENCE")
                    self.nbDigits = 1
            # horrible reverse-engineered condition to restart sequence at 1 digit
            if len(tmp) == 5 and tmp.startswith(b'\xdf\xdc\xdd\xd0'):
                self.nbDigits = 1
            # horrible experimentally-determined condition to change the toggle data set for the last byte
            if (self.fragmentIndex % 100 == 0):
                self.base_index = (self.base_index + 2) % 20
            packet = self.MESSAGE_CONTINUE_BEGIN + tmp + self.MESSAGE_CONTINUE_END
            self.sendContinuePacket(packet)

    def loop(self):
        try:
            while (self.socket_error == False):
                self.retrieveImage()
        except RestartException as resExc:
            print(("[ERROR] restarting global loop in %d seconds due to exception: %s" % (resExc.delay, resExc.msg)))
            # Let the camera breathe a bit before trying again
            time.sleep(resExc.delay)
            pass
        except KeyboardInterrupt:
            raise
        # end of global loop
