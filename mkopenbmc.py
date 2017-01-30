#!/usr/bin/env python
from argparse import ArgumentParser
import os
import sys
import subprocess
import binascii
import struct
import csv


def splitimage(data):
    partitions = []
    cursor = 0
    for part, size in imagetable:
        end = cursor + size
        partitions.append(imgdata[cursor:end])
        cursor = end
    return partitions


def gen_uboot_env(param_binary):
    while len(param_binary) < (131072 - 4):
        param_binary += '\x00'
    chksum = binascii.crc32(param_binary)
    bindata = struct.pack('<i', chksum) + param_binary
    return bindata


def write_network_config(address, gateway):
    filepath = 'squashfs-root/etc/systemd/network/00-bmc-eth0.network'
    template = ('[Match]\n' +
                'Name=eth0\n' +
                '[Network]\n' +
                'Address={0}\n' +
                'Gateway={1}\n')
    with open(filepath, 'w') as netconf:
        netconf.write(template.format(address, gateway))


def squash_rofs(output):
    subprocess.call(['mksquashfs', 'squashfs-root/', output, '-comp', 'xz'])


if os.getuid() != 0:
    print 'Run this as root, so that squashfs UIDs can be preserved'
    sys.exit(1)

desc = '''
Hacks a source OpenBMC image to include MAC and IP addresses from a csv table
'''.strip()

parser = ArgumentParser(description=desc)
parser.add_argument('source', help="Source image file", type=file)
parser.add_argument('csv', help="CSV table (mac,ip,gateway,output)", type=file)
args = parser.parse_args()

imagetable = (("uboot.img", 393216),
              ("uboot-env.img", 131072),
              ("kernel.img", 2621440),
              ("initrd.img", 1835008),
              ("rofs.img", 24379392),
              ("rwfs.img", 4194304))
expected_filesize = sum([x[1] for x in imagetable])

print "Reading source image"
imgdata = args.source.read()
if len(imgdata) != expected_filesize:
    errmsg = "Source file expected to be {0} bytes, is {1}"
    print errmsg.format(expected_filesize, len(imgdata))
    sys.exit(1)

uboot, ubootenv, kernel, initrd, rofs, rwfs = splitimage(imgdata)
print 'Writing out read only file system to rofs.img'
with open('rofs.img', 'w') as rofsfile:
    rofsfile.write(rofs)


uboot_parameters = ('baudrate=38400\x00' +
                    'bootargs=console=ttyS4,38400n8\x00' +
                    'root=/dev/ram rw\x00' +
                    'bootcmd=bootm 20080000 20300000\x00' +
                    'bootdelay=3\x00' +
                    'bootfile=all.bin\x00' +
                    'eeprom=y\x00' +
                    'ethact=aspeednic#0\x00' +
                    'ethaddr={ethaddr}\x00' +
                    'stderr=serial\x00' +
                    'stdin=serial\x00' +
                    'stdout=serial\x00' +
                    'verify=n')


print 'Unsquashing read only filesystem'
subprocess.call(['unsquashfs', 'rofs.img'])


csvreader = csv.reader(args.csv)
for row in csvreader:
    mac, ip, gateway, filename = row
    print 'Generating uboot env for {0}'.format(filename)
    ubootenv = gen_uboot_env(uboot_parameters.format(ethaddr=mac))
    write_network_config(ip, gateway)
    squash_rofs(filename + '.rofs')
    rofs = open(filename + '.rofs').read()
    while len(rofs) < 24379392:
        rofs += '\xff'
    with open(filename, 'w') as custom_image:
        for partition in [uboot, ubootenv, kernel, initrd, rofs, rwfs]:
            custom_image.write(partition)
    os.unlink(filename + '.rofs')

subprocess.call(['rm', '-fr', 'squashfs-root/', 'rofs.img'])
