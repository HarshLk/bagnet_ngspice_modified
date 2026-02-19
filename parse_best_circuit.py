
import argparse
import re
import ast

def parse_log_for_best_circuit(log_file_path):
    """
    Parses a BagNet log file to find the design with the overall best cost.

    Args:
        log_file_path (str): The path to the progress_logs.txt file.
    
    Returns:
        A dictionary containing the best design information found in the log,
        or None if no valid design information is found.
    """
    try:
        with open(log_file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Log file not found at '{log_file_path}'")
        return None

    best_overall_cost = float('inf')
    best_design_info = {}
    
    current_iteration_data = {}

    # Regex patterns to find the relevant lines
    cost_pattern = re.compile(r".*best_cost=\[(.*?)\]")
    spec_pattern = re.compile(r".*best_spec=(.*)")
    design_pattern = re.compile(r".*best_design=(.*)")

    for line in lines:
        cost_match = cost_pattern.match(line)
        if cost_match:
            try:
                # If we find a new cost, process the previously collected data
                if 'cost' in current_iteration_data and 'specs' in current_iteration_data and 'design' in current_iteration_data:
                    if current_iteration_data['cost'] < best_overall_cost:
                        best_overall_cost = current_iteration_data['cost']
                        best_design_info = current_iteration_data

                # Start a new data block
                current_iteration_data = {'cost': float(cost_match.group(1))}
            except (ValueError, IndexError):
                continue

        spec_match = spec_pattern.match(line)
        if spec_match:
            try:
                # ast.literal_eval is safer than eval
                current_iteration_data['specs'] = ast.literal_eval(spec_match.group(1))
            except (ValueError, SyntaxError):
                continue
        
        design_match = design_pattern.match(line)
        if design_match:
            try:
                # The design vector can be large and might need careful parsing
                design_str = design_match.group(1).strip()
                # A simple ast.literal_eval might fail if the format is unusual.
                # Let's try to make it more robust.
                design_str = design_str.replace('\\n', '').replace('\\n', '').strip()
                current_iteration_data['design'] = ast.literal_eval(design_str)

            except (ValueError, SyntaxError):
                continue
    
    # Check the last collected data block after the loop finishes
    if 'cost' in current_iteration_data and 'specs' in current_iteration_data and 'design' in current_iteration_data:
        if current_iteration_data['cost'] < best_overall_cost:
            best_overall_cost = current_iteration_data['cost']
            best_design_info = current_iteration_data
            
    return best_design_info if best_design_info else None

def main():
    """Main function to run the parser from the command line."""
    parser = argparse.ArgumentParser(
        description="Parse a BagNet log file to extract the best circuit design."
    )
    parser.add_argument(
        "logfile",
        help="Path to the log file (e.g., outputs/log/.../progress_logs.txt)"
    )
    args = parser.parse_args()

    best_circuit = parse_log_for_best_circuit(args.logfile)

    if best_circuit:
        print("="*50)
        print("              Best Circuit Found in Log")
        print("="*50)
        print(f"\nCost: {best_circuit['cost']}\n")
        print("Specifications:")
        for spec, value in best_circuit['specs'].items():
            print(f"  - {spec:<8}: {value}")
        print("\nDesign Parameters (x):")
        print(best_circuit['design'])
        print("\n"+"="*50)
    else:
        print("Could not find any valid circuit information in the log file.")

if __name__ == "__main__":
    main()
