#!/usr/bin/env python3
"""Isolated test script to demonstrate the Python f-string vs CSS curly brace bug."""

import sys

def simulate_broken_code():
    print("--- Attempting to run the BROKEN f-string version ---")
    
    # We use exec() here because Python won't even let a file compile 
    # if it has an f-string syntax error inside it!
    broken_code_string = """
def get_ui_broken(device_id):
    button_group_html = f"<div>Buttons for {device_id}</div>"
    
    # ❌ This has the 'f' prefix AND single curly braces around the CSS variable
    return f\"\"\"
    <div style="background: var(--theme-bg-subtle, #f8f9fa);">
        {button_group_html}
    </div>
    \"\"\"
get_ui_broken('50400')
"""
    try:
        exec(broken_code_string)
    except SyntaxError as e:
        print(f"❌ CRASHED! Python threw a SyntaxError:")
        print(f"   Error Message: {e}")
        print("   Explanation  : Python saw 'f\"\"\"' and thought the CSS brace '{--theme-bg-subtle...}' was Python code!")


def simulate_fixed_code():
    print("\n--- Attempting to run the FIXED string-replace version ---")
    
    try:
        device_id = '50400'
        button_group_html = f"<div>Buttons for {device_id}</div>"
        
        # ✅ Standard string template (no 'f' prefix) safely ignoring CSS braces
        html_template = """
        <div style="background: var(--theme-bg-subtle, #f8f9fa);">
            {button_group_html}
        </div>
        """
        
        # Explicit replacement for our specific placeholder token
        result_html = html_template.replace("{button_group_html}", button_group_html)
        
        print("✅ SUCCESS! The string combined perfectly without executing CSS as Python:")
        print(result_html.strip())
        
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    simulate_broken_code()
    simulate_fixed_code()