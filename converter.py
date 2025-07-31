import re
import os
import json
import argparse
from collections import defaultdict

def parse_connections(data):
    """
    Parses the Eulerian path string to build a map of component connections.
    """
    path = data.strip().split('->')
    components = defaultdict(dict)
    
    # Regex to identify component terminals, e.g., NM1_D, R1_P
    terminal_regex = re.compile(r"^(NM|PM|R|C)(\d+)_([DGSBPN])$")

    for i, part in enumerate(path):
        match = terminal_regex.match(part)
        if not match:
            continue

        comp_type, comp_num, term_type = match.groups()
        comp_name = f"{comp_type}{comp_num}"

        # Find connection for the terminal from previous part in path
        if i > 0:
            prev_part = path[i-1]
            prev_match = terminal_regex.match(prev_part)
            is_prev_part_of_same_comp = False
            if prev_match:
                 # Check if prev_part is like NM1_B and part is NM1
                 if f"{prev_match.group(1)}{prev_match.group(2)}" == comp_name:
                     is_prev_part_of_same_comp = True
            
            if prev_part != comp_name and not is_prev_part_of_same_comp:
                # If a terminal is already assigned, it implies a shared node.
                # We will keep the first connection found.
                if term_type not in components[comp_name]:
                    components[comp_name][term_type] = prev_part

        # Find connection for the terminal from next part in path
        if i < len(path) - 1:
            next_part = path[i+1]
            next_match = terminal_regex.match(next_part)
            is_next_part_of_same_comp = False
            if next_match:
                if f"{next_match.group(1)}{next_match.group(2)}" == comp_name:
                    is_next_part_of_same_comp = True

            if next_part != comp_name and not is_next_part_of_same_comp:
                if term_type not in components[comp_name]:
                    components[comp_name][term_type] = next_part
                    
    return components

def generate_spice_netlist(components):
    """
    Generates a SPICE netlist from the component connection data.
    """
    netlist = ["* Generated SPICE netlist"]
    
    # Sort components by type and number for consistent output
    sorted_comp_names = sorted(components.keys(), key=lambda x: (re.match(r"([A-Z]+)(\d+)", x).group(1), int(re.match(r"([A-Z]+)(\d+)", x).group(2))))

    for name in sorted_comp_names:
        conns = components[name]
        if name.startswith('NM'):
            # Netlist format for NMOS: M<name> <drain> <gate> <source> <body> <model>
            line = f"M{name[2:]} {conns.get('D', 'NC')} {conns.get('G', 'NC')} {conns.get('S', 'NC')} {conns.get('B', 'NC')} nmos_model"
            netlist.append(line)
        elif name.startswith('PM'):
            # Netlist format for PMOS: M<name> <drain> <gate> <source> <body> <model>
            line = f"M{name[2:]} {conns.get('D', 'NC')} {conns.get('G', 'NC')} {conns.get('S', 'NC')} {conns.get('B', 'NC')} pmos_model"
            netlist.append(line)
        elif name.startswith('R'):
            # Netlist format for Resistor: R<name> <pos> <neg> <value>
            line = f"R{name[1:]} {conns.get('P', 'NC')} {conns.get('N', 'NC')} 1k" # Default value 1k
            netlist.append(line)
        elif name.startswith('C'):
            # Netlist format for Capacitor: C<name> <pos> <neg> <value>
            line = f"C{name[1:]} {conns.get('P', 'NC')} {conns.get('N', 'NC')} 1p" # Default value 1p
            netlist.append(line)

    netlist.append(".END")
    return "\n".join(netlist)

def generate_netlistsvg_json(components):
    """
    Generates a netlistsvg-compatible JSON from the component connection data.
    """
    nets = set()
    for comp, conns in components.items():
        for term, net in conns.items():
            nets.add(net)

    # Assign a unique integer ID to each net
    net_map = {name: i for i, name in enumerate(sorted(list(nets)), 1)}

    ports = {}
    # Identify top-level ports based on common naming conventions
    for net_name in sorted(list(nets)):
        bits = [net_map[net_name]]
        direction = "inout"  # Default direction

        if net_name.upper().startswith("VOUT"):
            direction = "output"
        elif any(net_name.upper().startswith(p) for p in ["VDD", "VSS", "GND", "VIN", "VCLK", "VB", "IB"]):
            direction = "input"
        
        # We will consider all nets that seem to be I/O or power as ports for visualization
        if direction != "inout" or net_name.upper() in ['VDD', 'VSS']:
            ports[net_name] = {"direction": direction, "bits": bits}

    cells = {}
    sorted_comp_names = sorted(components.keys(), key=lambda x: (re.match(r"([A-Z]+)(\d+)", x).group(1), int(re.match(r"([A-Z]+)(\d+)", x).group(2))))

    for comp_name in sorted_comp_names:
        conns = components[comp_name]
        cell = {}
        port_directions = {}
        connections = {}

        type_map = {
            'NM': 'nmos',
            'PM': 'pmos',
            'R': 'resistor',
            'C': 'capacitor'
        }
        comp_type_prefix = re.match(r"([A-Z]+)", comp_name).group(1)
        cell["type"] = type_map.get(comp_type_prefix, "unknown")
        
        if comp_type_prefix in ['NM', 'PM']:
            port_directions = {"D": "input", "G": "input", "S": "input", "B": "input"}
        elif comp_type_prefix in ['R', 'C']:
            port_directions = {"P": "input", "N": "input"}

        for term, net in conns.items():
            if net in net_map:
                connections[term] = [net_map[net]]

        cell["port_directions"] = port_directions
        cell["connections"] = connections
        cells[comp_name] = cell
    
    netlist_json = {
        "modules": {
            "top": {
                "ports": ports,
                "cells": cells
            }
        }
    }
    
    return json.dumps(netlist_json, indent=2)


def main():
    """
    Main function to read data from all .txt files in a directory, 
    parse it, and generate the SPICE or JSON files.
    """
    parser = argparse.ArgumentParser(description="Convert circuit description to SPICE or netlistsvg JSON format.")
    parser.add_argument("input_dir", help="Input directory path containing .txt files (e.g., data/)")
    parser.add_argument("--format", choices=['spice', 'json'], default='spice', help="Output format (spice or json)")
    parser.add_argument("--output_dir", default='output', help="Output directory path.")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_format = args.format
    output_dir = args.output_dir

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory not found at {input_dir}")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    txt_files = [f for f in os.listdir(input_dir) if f.endswith('.txt')]
    if not txt_files:
        print(f"No .txt files found in {input_dir}")
        return

    for filename in txt_files:
        input_file = os.path.join(input_dir, filename)
        
        base_name = os.path.basename(input_file)
        file_name_without_ext = os.path.splitext(base_name)[0]
        
        if output_format == 'spice':
            output_file = os.path.join(output_dir, f"{file_name_without_ext}_spice.sp")
        else:
            output_file = os.path.join(output_dir, f"{file_name_without_ext}.json")

        print(f"Processing {input_file} -> {output_file}")

        with open(input_file, 'r') as f:
            data = f.read()

        components = parse_connections(data)

        if output_format == 'spice':
            netlist_content = generate_spice_netlist(components)
        else:
            netlist_content = generate_netlistsvg_json(components)

        with open(output_file, 'w') as f:
            f.write(netlist_content)

        print(f"Successfully generated {output_format.upper()} netlist at {output_file}")

if __name__ == '__main__':
    main() 