import os

def parse_ir_file(file_path):
    """
    Analiza un archivo .ir de Flipper Zero y devuelve una lista de comandos.
    
    Args:
        file_path (str): La ruta al archivo .ir.
        
    Returns:
        list: Una lista de diccionarios, donde cada diccionario representa un comando
              y contiene claves como 'name', 'type', 'protocol', 'address', 'command'.
    """
    commands = []
    current_command = {}
    
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # If we encounter a 'name' field, it usually starts a new command block
                # (except for the file header, but usually file header doesn't have 'name' 
                # in the same way as commands, or we can handle it).
                # Actually, Flipper IR files have a header section and then repeated sections for buttons.
                # The header usually has 'Filetype', 'Version'.
                # Button sections start with 'name'.
                
                if key == 'name':
                    if current_command:
                        commands.append(current_command)
                    current_command = {}
                    current_command['name'] = value
                else:
                    if current_command is not None:
                         current_command[key] = value
                         
        # Append the last command if exists
        if current_command:
            commands.append(current_command)
            
    except Exception as e:
        print(f"Error parsing file {file_path}: {e}")
        return []

    return commands

if __name__ == "__main__":
    # Test with a dummy file or path if needed
    pass
