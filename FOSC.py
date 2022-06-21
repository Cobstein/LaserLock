
from mcculw import ul
from mcculw.enums import DigitalIODirection
from digital import DigitalProps, PortInfo
import time


##This example function shows how to use the MCC board API
# to change the channel on the Bristol Instruments Fiber Switch
# must run pip install mcculw
# see also: https://pypi.org/project/mcculw/
def run_example():
    # InstaCal board number
    board_num = 0

    digital_props = DigitalProps(board_num)

    port = next(
            (port for port in digital_props.port_info
             if port.supports_output), None)

    if port == None:
        print("unsupported board")
        return -1
    if port.is_port_configurable:
        ul.d_config_port(board_num, port.type, DigitalIODirection.OUT)

    port_value = 0
    
    print("change to channel {}".format(port_value + 1))
    ul.d_out(board_num, port.type, port_value)

if __name__ == '__main__':
    run_example()
