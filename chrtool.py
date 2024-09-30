import struct
import os
import sys
import fnmatch

'''
Dead or Alive 2 - CHR extractor / builder
'''
'''
MIT License

Copyright (c) 2024 VincentNL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

debug = False

def read_uint32(f):
    return struct.unpack('<I', f.read(4))[0]


def build_chr(input_folder, output_folder):
    folder_name = os.path.basename(input_folder)

    if len(folder_name) == 5:
        char_flag = True
    else:
        char_flag = False

    chr_header = b'\x18\00\00\00'  # magic

    mdl_ram_var = 0x0c300000 if char_flag else 0x0c400000
    pvr_ram_var = 0x0d200000 if char_flag else 0x0d600000

    model_data = b''
    model_pointers = b'\x00' * 8
    model_ptr_val = mdl_ram_var
    model_size = 0

    pvr_data = b''
    pvr_headers = b''
    pvr_ptr_val = pvr_ram_var
    pvr_size = 0

    bin_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith('.bin')]
    num_bin_files = len(bin_files)

    for bin_file in bin_files:
        with open(bin_file, 'rb') as model:
            model_ptr_val = model_size + mdl_ram_var
            model_pointers += struct.pack('<I', model_ptr_val)
            model_size += len(model.read())
            model.seek(0x0)
            model_data += model.read()

    chr_header += struct.pack('<I', model_size + 0x20)  # header pointer of model pointers
    chr_header += struct.pack('<I', (model_size + 0x20) + num_bin_files * 0x4)  # header pointer of model pointers
    chr_header += struct.pack('<I', num_bin_files)  # header ttl models

    try:
        pvr_files = [os.path.join(input_folder, 'Textures', f) for f in
                     os.listdir(os.path.join(input_folder, 'Textures')) if f.lower().endswith('.pvr')]
        num_pvr_files = len(pvr_files)
    except FileNotFoundError:
        num_pvr_files = 0

    chr_header += struct.pack('<I', num_pvr_files)  # header ttl pvrs
    chr_header += b'\x00' * 4  # padding

    for pvr_file in pvr_files:
        with open(pvr_file, 'rb') as pvr:
            magic = pvr.read(0x4)
            pvr_var = 0 if magic == b'PVRT' else 0x10

            pvr.seek(pvr_var + 0xc)  # PVR resolution
            pvr_resolution = pvr.read(4)
            pvr_headers += pvr_resolution

            pvr.seek(pvr_var + 0x8)  # PVR pixel type
            pvr_pixel_type = pvr.read(4)
            pvr_headers += pvr_pixel_type

            pvr_ptr_val = pvr_size + pvr_ram_var  # ram pointer
            pvr_headers += struct.pack('<I', pvr_ptr_val)

            pvr.seek(pvr_var + 0x10)
            pvr_size += len(pvr.read())
            pvr.seek(pvr_var + 0x10)
            pvr_data += pvr.read()

    with open(os.path.join(output_folder, f'{folder_name}.chr'), 'wb') as chr_file:
        chr_data = chr_header + model_data + model_pointers + pvr_headers + b'\x00' * 4
        chr_file.write(chr_data)

    with open(os.path.join(output_folder, f'{folder_name}.bin'), 'wb') as bin_file:
        bin_file.write(pvr_data)
    print(f'Build complete for: {folder_name}!')


def save_pvr(A, bin, chr, PVR_start, PVR_size, pixel_type, tex_size, extraction_folder, name):
    bin.seek(PVR_start)
    PVR_size_val = PVR_size + 0x8
    MEMORY_FILE = bytearray(b'PVRT')
    MEMORY_FILE += struct.pack("<L", PVR_size_val)
    MEMORY_FILE += struct.pack("<L", pixel_type)
    MEMORY_FILE += struct.pack("<L", tex_size)
    MEMORY_FILE += bin.read(PVR_size)

    texture_folder = os.path.join(extraction_folder, name, "Textures")
    if not os.path.exists(texture_folder):
        os.makedirs(texture_folder)

    with open(os.path.join(texture_folder, f"TexID_{str(A).zfill(3)}.PVR"), "wb") as f:
        f.write(MEMORY_FILE)


def ext_texture(pvr_container, chr_file, extraction_folder, name):
    with open(pvr_container, "rb") as bin:
        binsize = len(bin.read())
        with open(chr_file, "rb") as chr:
            chr.seek(0x10)
            total_tex = read_uint32(chr)
            chr.seek(0x8)
            PVR_header_offset = read_uint32(chr)
            chr.seek(PVR_header_offset + 0x8)
            base_address = read_uint32(chr)
            chr.seek(PVR_header_offset)

            for A in range(total_tex):
                tex_size = read_uint32(chr)
                pixel_type = read_uint32(chr)
                PVR_start = read_uint32(chr) - base_address

                if A < total_tex - 1:
                    nextpos = chr.tell() + 0x8
                    chr.seek(nextpos)
                    PVR_end = read_uint32(chr) - base_address
                    PVR_size = PVR_end - PVR_start
                    nextpos -= 0x8
                    chr.seek(nextpos)
                else:
                    PVR_end = binsize
                    PVR_size = PVR_end - PVR_start

                save_pvr(A, bin, chr, PVR_start, PVR_size, pixel_type, tex_size, extraction_folder, name)


def ext_models(chr_file, extraction_folder, name):
    with open(chr_file, "rb") as chr:
        chr.seek(0xc)
        total_models = read_uint32(chr)
        chr.seek(0x4)
        models_pointers = read_uint32(chr)
        chr.seek(models_pointers)
        base_address = read_uint32(chr)
        model_offset_ptr = models_pointers

        for A in range(total_models):
            chr.seek(model_offset_ptr)
            model_start = (read_uint32(chr) - base_address) + 0x18

            if A < total_models - 1:
                next_offset = read_uint32(chr)
                model_end = (next_offset - base_address) + 0x18
            else:
                model_end = models_pointers - 0x8

            model_size = model_end - model_start
            chr.seek(model_start)

            model_folder = os.path.join(extraction_folder, name)
            if not os.path.exists(model_folder):
                os.makedirs(model_folder)

            with open(os.path.join(model_folder, f"model_{name}_{str(A).zfill(3)}.bin"), "wb") as f:
                f.write(chr.read(model_size))

            model_offset_ptr += 0x4


def extract_chr_files(chr_files, extraction_folder):
    for chr_file_path in chr_files:
        name = os.path.splitext(os.path.basename(chr_file_path))[0]
        pvr_container = f"{chr_file_path[:-4]}.bin"

        ext_texture(pvr_container, chr_file_path, extraction_folder, name)
        ext_models(chr_file_path, extraction_folder, name)
        print(f'{chr_file_path} Extraction complete!')


def print_cli_screen():
    print("┌─────────────────────────────┐")
    print("│     * CHR TOOL v1.0 *       │")
    print("│       Dead or Alive 2       │")
    print("├─────────────────────────────┤")
    print("│     VincentNL 2024/02/30    │")
    print("├─────────────────────────────┤")
    print("│   ♥ ko-fi.com/vincentnl     │")
    print("│   ♥ patreon.com/vincentnl   │")
    print("└─────────────────────────────┘")

def error_msg():
    print('###  No valid option specified! ###')
    print()
    print('  For HELP and USAGE OPTIONS:')
    print('       > chrtool -h')
    print()

def print_help_screen():
    print()
    print('------------------')
    print('  HELP AND USAGE  ')
    print('------------------')
    print('  1. CHR EXTRACT')
    print('------------------')
    print('  Extract contents of .CHR files.')
    print()
    print('  > chrtool -e [CHR_file] [out_folder]')
    print()
    print('  Example 1 ( single file ): ')
    print('       > chrtool -e "c:\\doa2\\mod\\AYA00.CHR" "c:\\doa2\\mod\\new"\n')
    print('  Example 2 ( multiple files ): ')
    print('       > chrtool -e "c:\\doa2\\mod\\AYA00.CHR,c:\\doa2\\mod\\AYA01.CHR" "c:\\doa2\\mod\\new"\n')
    print('  Example 3 ( all files ): ')
    print('       > chrtool -e "c:\\doa2\\mod\\*.*" "c:\\doa2\\mod\\new"\n')
    print('----------------')
    print('  2. CHR BUILD')
    print('------------------')
    print()
    print('  Convert a folder, containing models(.bin) and textures(.PVR) into a .CHR file ')
    print('  Please note the input folder must contain:')
    print('       1. "model_xxxx.bin" files')
    print('       2. "Textures" folder with .PVR files')
    print()
    print('  > chrtool -r [CHR_folder] [out_folder]')
    print()
    print('  Example 1 ( single folder ):')
    print('       > chrtool -r "c:\\doa2\\mod\\AYA00" "c:\\doa2\\mod\\new"')
    print()
    print('  Example 2: ( multiple folders )')
    print('       > chrtool -r "c:\\doa2\\mod\\AYA00,c:\\doa2\\mod\\AYA01" "c:\\doa2\\mod\\new"')
    print()
    print('  Example 3: ( all folders )')
    print('       > chrtool -r "c:\\doa2\\mod\\*.*" "c:\\doa2\\mod\\new"\n')


def main():
    # Only print the logo once at the start
    print_cli_screen()

    if len(sys.argv) < 2:
        error_msg()
        sys.exit(0)

    # Check for help flag
    if len(sys.argv) == 2 and sys.argv[1] == '-h':
        print_help_screen()
        sys.exit(0)

    if len(sys.argv) == 2 and sys.argv[1] != '-h':
        error_msg()
        sys.exit(0)

    # Initialize variables
    operation = ""
    chr_files_input = ""
    extraction_folder = os.getcwd()  # Default to current working directory

    # Extraction Handling
    if len(sys.argv) == 3 and sys.argv[1] == '-e':
        operation = sys.argv[1]
        chr_files_input = sys.argv[2].strip('"')

    elif len(sys.argv) == 4 and sys.argv[1] == '-e':
        operation = sys.argv[1]
        chr_files_input = sys.argv[2].strip('"')
        extraction_folder = sys.argv[3].strip('"')

    # Rebuilding Handling
    elif len(sys.argv) == 3 and sys.argv[1] == '-r':
        operation = sys.argv[1]
        input_folders_input = sys.argv[2].strip('"')

    elif len(sys.argv) == 4 and sys.argv[1] == '-r':
        operation = sys.argv[1]
        input_folders_input = sys.argv[2].strip('"')
        output_folder = sys.argv[3].strip('"')
    else:
        print_cli_screen()
        sys.exit(1)

    # Execute the appropriate operation
    if operation == "-e":
        # Handle multiple CHR files input
        chr_files = []

        # Wildcard handling
        if '*' in chr_files_input:
            path = os.getcwd()  # Use current working directory
            ext = chr_files_input.split('*')[-1]  # Get the extension part if any
            chr_files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.chr')]
        else:
            chr_files = [f.strip('"') for f in chr_files_input.split(',')]
            chr_files = [f for f in chr_files if f.lower().endswith('.chr')]

        # Create extraction folder if it doesn't exist
        if not os.path.exists(extraction_folder):
            os.makedirs(extraction_folder)

        extract_chr_files(chr_files, extraction_folder)

    elif operation == "-r":
        # Default output folder to current working directory if not provided
        output_folder = os.getcwd() if 'output_folder' not in locals() else output_folder

        # Handle multiple input folders
        input_folders = [f.strip('"') for f in input_folders_input.split(',')]

        for folder in input_folders:
            if os.path.isdir(folder):
                build_chr(folder, output_folder)
            else:
                print(f"Warning: {folder} is not a valid directory.")

if __name__ == "__main__":
    main()
