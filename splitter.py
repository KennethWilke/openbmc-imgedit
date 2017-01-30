import sys

imagetable = (("uboot.img", 393216),
              ("uboot-env.img", 131072),
              ("kernel.img", 2621440),
              ("initrd.img", 1835008),
              ("rofs.img", 24379392),
              ("rwfs.img", 4194304))


with open(sys.argv[1]) as source:
    for image, size in imagetable:
        with open(image, 'w') as img:
            img.write(source.read(size))
