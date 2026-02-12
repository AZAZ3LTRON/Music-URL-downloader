import os
from colorama import init, Fore, Back, Style

init(autoreset=True)

class Enhanced_Menu:
    """An enhanced menu system for better program interaction"""
    def __init__(self):
        self.current_theme = 'default'

    # Predefined color combinations
    COLORS = {
        'header': f"{Fore.CYAN}{Style.BRIGHT}",
        'title': f"{Fore.MAGENTA}{Style.BRIGHT}",
        'section': f"{Fore.BLUE}{Style.BRIGHT}",
        'menu_item': f"{Fore.YELLOW}",
        'menu_desc': f"{Fore.WHITE}",
        'success': f"{Fore.GREEN}{Style.BRIGHT}",
        'failure': f"{Fore.RED}{Style.BRIGHT}",
        'error': f"{Fore.YELLOW}{Style.BRIGHT}",
        'info': f"{Fore.CYAN}",
        'input': f"{Fore.GREEN}{Style.BRIGHT}",
        'highlight': f"{Fore.YELLOW}{Style.BRIGHT}",
        'dim': f"{Style.DIM}",
    }

    @staticmethod
    def clear_screen():
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_color(text, color_type='info', bold=False, end='\n'):
        """Print colored text"""
        color_code = Enhanced_Menu.COLORS.get(color_type, Enhanced_Menu.COLORS['info'])
        if bold and 'BRIGHT' not in color_code:
            text = f"{Style.BRIGHT}{text}"
        print(f"{color_code}{text}{Style.RESET_ALL}", end=end)

    @staticmethod
    def print_boxed_title(title, width=60):
        """Print a title in a decorative box"""
        border = "═" * (width - 2)
        print(f"{Enhanced_Menu.COLORS['title']}╔{border}╗")
        padding = width - len(title) - 4
        left_pad = padding // 2
        right_pad = padding - left_pad
        print(f"{Enhanced_Menu.COLORS['title']}║{' ' * left_pad}{title}{' ' * right_pad}║")
        print(f"{Enhanced_Menu.COLORS['title']}╚{border}╝{Style.RESET_ALL}")

    @staticmethod
    def print_header(title, subtitle=""):
        """Print a formatted header"""
        print()
        Enhanced_Menu.print_boxed_title(title)
        if subtitle:
            print(f"\n{Enhanced_Menu.COLORS['info']}{subtitle}{Style.RESET_ALL}")
        print()

    @staticmethod
    def print_section(title, symbol="─"):
        """Print a section header"""
        print(f"\n{Enhanced_Menu.COLORS['section']}{symbol * 60}")
        print(f"  {title}")
        print(f"{symbol * 60}{Style.RESET_ALL}")

    @staticmethod
    def print_menu_item(number, title, description="", indent=2):
        """Print a menu item with number and description"""
        indent_str = " " * indent
        print(f"{indent_str}{Enhanced_Menu.COLORS['menu_item']}[{number:2}]{Style.RESET_ALL} "
              f"{Enhanced_Menu.COLORS['menu_item']}{Style.BRIGHT}{title}{Style.RESET_ALL}")
        if description:
            desc_indent = " " * (indent + 5)
            wrapped_desc = Enhanced_Menu.wrap_text(description, width=50)
            for line in wrapped_desc:
                print(f"{desc_indent}{Enhanced_Menu.COLORS['menu_desc']}{line}{Style.RESET_ALL}")

    @staticmethod
    def wrap_text(text, width=50):
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    @staticmethod
    def print_status(message, status_type="info", icon=""):
        """Print a status message with appropriate color and icon"""
        status_config = {
            "success": {"color": "success", "default_icon": "✓"},
            "failure": {"color": "failure", "default_icon": "✗"},
            "error": {"color": "error", "default_icon": "⚠"},
            "info": {"color": "info", "default_icon": "ℹ"}
        }
        config = status_config.get(status_type, status_config["info"])
        icon_to_use = icon or config["default_icon"]
        print(f"{Enhanced_Menu.COLORS[config['color']]}{icon_to_use} {message}{Style.RESET_ALL}")

    @staticmethod
    def get_input(prompt, input_type="int", min_val=None, max_val=None, default=None):
        """Get validated user input with colored prompt"""
        prompt_color = Enhanced_Menu.COLORS['input']
        reset = Style.RESET_ALL
        while True:
            try:
                full_prompt = f"{prompt_color}{prompt}{reset}"
                if default is not None:
                    full_prompt += f" [{Fore.YELLOW}{default}{reset}]"
                full_prompt += f"{prompt_color}:{reset} "
                user_input = input(full_prompt).strip()
                if not user_input and default is not None:
                    return default
                if input_type == "int":
                    value = int(user_input)
                    if min_val is not None and value < min_val:
                        raise ValueError(f"Value must be at least {min_val}")
                    if max_val is not None and value > max_val:
                        raise ValueError(f"Value must be at most {max_val}")
                    return value
                elif input_type == "str":
                    return user_input
                elif input_type == "yn":
                    if user_input.lower() in ['y', 'yes', '']:
                        return True
                    elif user_input.lower() in ['n', 'no']:
                        return False
                    else:
                        raise ValueError("Please enter 'y' or 'n'")
                elif input_type == "float":
                    return float(user_input)
                else:
                    return user_input
            except ValueError as e:
                Enhanced_Menu.print_status(str(e), "error")
                continue
            except KeyboardInterrupt:
                Enhanced_Menu.print_status("Operation cancelled by user", "error")
                return None
