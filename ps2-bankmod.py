import os
import sys
import struct

def get_u16_le(buf, offset):
    return struct.unpack("<H", buf[offset:offset+2])[0]

def get_u16_be(buf, offset):
    return struct.unpack(">H", buf[offset:offset+2])[0]

def get_u32_le(buf, offset):
    return struct.unpack("<I", buf[offset:offset+4])[0]

def get_u32_be(buf, offset):
    return struct.unpack(">I", buf[offset:offset+4])[0]

def put_u16_le(buf, offset, value):
    buf[offset:offset+2] = struct.pack("<H", value)

def put_u16_be(buf, offset, value):
    buf[offset:offset+2] = struct.pack(">H", value)

def put_u32_le(buf, offset, value):
    buf[offset:offset+4] = struct.pack("<I", value)

def put_u32_be(buf, offset, value):
    buf[offset:offset+4] = struct.pack(">I", value)

def get_vag_param_offset(hdbuf, vagi_chunk_offset, index):
    return get_u32_le(hdbuf, vagi_chunk_offset + 0x10 + (index * 4))

def get_vag_offset(hdbuf, vagi_chunk_offset, index):
    return get_u32_le(hdbuf, vagi_chunk_offset + get_vag_param_offset(hdbuf, vagi_chunk_offset, index) + 0x00)

def get_vag_sample_rate(hdbuf, vagi_chunk_offset, index):
    return get_u16_le(hdbuf, vagi_chunk_offset + get_vag_param_offset(hdbuf, vagi_chunk_offset, index) + 0x04)

def put_vag_offset(hdbuf, vagi_chunk_offset, index, vag_offset):
    put_u32_le(hdbuf, vagi_chunk_offset + get_vag_param_offset(hdbuf, vagi_chunk_offset, index) + 0x00, vag_offset)

def put_vag_sample_rate(hdbuf, vagi_chunk_offset, index, sample_rate):
    put_u16_le(hdbuf, vagi_chunk_offset + get_vag_param_offset(hdbuf, vagi_chunk_offset, index) + 0x04, sample_rate)

def isnum(n):
    try:
        int(n)
    except ValueError:
        return False
    return True

def get_file_arg(message, real=True):
    x = ''
    while not os.path.isfile(x):
        x = input(message).strip('"')
    return os.path.realpath(x)

def get_dir_arg(message, real=True):
    x = ''
    while not os.path.isdir(x):
        x = input(message).strip('"')
    return os.path.realpath(x)

def get_num_arg(message, negative=False):
    x = ''
    while not isnum(x) or (not negative and int(x) < 0):
        x = input(message)
    return int(x)

def get_lit_arg(valid_list, message, lowercase=True):
    x = ''
    while x not in valid_list:
        x = input(message)
        if lowercase:
            x = x.lower()
    return x

mode = get_lit_arg(['e','i'], "Enter 'e' to extract, 'i' to import: ")

hd_path = get_file_arg("Enter path to .HD file: ")
if not os.access(hd_path, os.R_OK):
    input("Could not open .HD file")
    sys.exit(1)

bd_path = get_file_arg("Enter path to .BD file: ")
if not os.access(bd_path, os.R_OK):
    input("Could not open .BD file")
    sys.exit(1)

with open(hd_path, "rb") as hd:
    hdbuf = bytearray( hd.read() )

with open(bd_path, "rb") as bd:
    bdbuf = bytearray( bd.read() )

if hdbuf[0x00:0x08] != b"IECSsreV":
    input("Unexpected ID at 0x00 in .HD")

if hdbuf[0x10:0x18] != b"IECSdaeH":
    input("Unexpected ID at 0x10 in .HD")

bd_size = get_u32_le(hdbuf, 0x20)

vagi_chunk_offset = get_u32_le(hdbuf, 0x30)

max_vag_index = get_u32_le(hdbuf, vagi_chunk_offset + 0x0C)

if mode == 'e':
    out_dir = get_dir_arg("Enter path to destination folder (must exist): ")
    if not os.access(out_dir, os.W_OK):
        input("Can not write to the specified folder!")
        sys.exit(1)

    bd_stem = os.path.splitext(bd_path)[0]

    bd_basename = os.path.basename(bd_stem)

    out_stem = os.path.join(out_dir, bd_basename)

    for vag_index in range(max_vag_index+1):
        vag_offset = get_vag_offset(hdbuf, vagi_chunk_offset, vag_index)

        if vag_index < max_vag_index:
            vag_size = get_vag_offset(hdbuf, vagi_chunk_offset, vag_index+1) - vag_offset
        else:
            vag_size = bd_size - vag_offset

        sample_rate = get_vag_sample_rate(hdbuf, vagi_chunk_offset, vag_index)

        header = bytearray(0x30)
        header[0x00:0x04] = b"VAGp"
        put_u32_be(header, 0x04, 0x20)
        put_u32_be(header, 0x0C, vag_size)
        put_u32_be(header, 0x10, sample_rate)

        with open("%s_%02d.VAG" % (out_stem, vag_index), "wb") as vag:
            vag.write(header + bdbuf[vag_offset:vag_offset+vag_size])

elif mode == 'i':
    in_vag_path = get_file_arg("Enter path to .VAG file (sound to import): ")
    if not os.access(in_vag_path, os.R_OK):
        input("Could not open .VAG file")
        sys.exit(1)

    with open(in_vag_path, "rb") as in_vagf:
        in_vag_header = in_vagf.read(0x30)
        # body_size = get_u32_be(in_vag_buf, 0x0C)
        in_vag_rate = get_u32_be(in_vag_header, 0x10)
        in_adpcm_buf = in_vagf.read()

    in_adpcm_size = len(in_adpcm_buf)

    target_vag_index = get_num_arg("Enter the sample to replace (index number): ")
    if target_vag_index > max_vag_index:
        input("Specified sample index exceeds max index")
        sys.exit(1)

    target_vag_offset = get_vag_offset(hdbuf, vagi_chunk_offset, target_vag_index)
    if target_vag_index < max_vag_index:
        target_vag_size = get_vag_offset(hdbuf, vagi_chunk_offset, target_vag_index+1) - target_vag_offset
    else:
        target_vag_size = bd_size - target_vag_offset

    # update sample rate
    put_vag_sample_rate(hdbuf, vagi_chunk_offset, target_vag_index, in_vag_rate)

    # update offsets for subsequent samples
    for sub_vag_index in range(target_vag_index+1, max_vag_index+1):
        sub_vag_offset = get_vag_offset(hdbuf, vagi_chunk_offset, sub_vag_index)
        put_vag_offset(hdbuf, vagi_chunk_offset, sub_vag_index, (sub_vag_offset - target_vag_size) + in_adpcm_size)

    # update BD size
    put_u32_le(hdbuf, 0x20, (bd_size - target_vag_size) + in_adpcm_size)

    with open(hd_path, "wb") as hd:
        hd.write(hdbuf)

    with open(bd_path, "wb") as bd:
        bd.write(bdbuf[:target_vag_offset])
        bd.write(in_adpcm_buf)
        bd.write(bdbuf[target_vag_offset+target_vag_size:bd_size])
        bd.truncate()

input("All done.")