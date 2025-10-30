# Contributing to Mesh Annotation Layers

Thank you for your interest in contributing to Mesh Annotation Layers! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

---

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect differing viewpoints and experiences
- Accept responsibility and apologize for mistakes

---

## How to Contribute

There are many ways to contribute:

1. **Report Bugs**: Help us identify and fix issues
2. **Suggest Features**: Share ideas for improvements
3. **Write Documentation**: Improve or translate documentation
4. **Submit Code**: Fix bugs or implement features
5. **Test**: Test new features and report findings
6. **Spread the Word**: Tell others about the addon

---

## Development Setup

### Prerequisites

- Blender 3.0 or higher
- Git for version control
- Text editor or IDE (VS Code, PyCharm, etc.)
- Basic Python knowledge

### Getting Started

1. **Fork the Repository**
   ```bash
   # Click "Fork" on GitHub, then clone your fork:
   git clone https://github.com/YOUR_USERNAME/Mesh-Annotation-Layers.git
   cd Mesh-Annotation-Layers
   ```

2. **Create a Development Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Set Up Development Environment**
   - Symlink the `mesh_annotation_layers` folder to your Blender addons directory
   - Or develop directly in the addons directory

4. **Enable Developer Extras in Blender**
   - Edit → Preferences → Interface → Developer Extras (checkbox)
   - This enables console output and developer tools

### Testing Your Changes

1. Open Blender
2. If addon is already installed, reload it:
   - F3 → "Reload Scripts"
   - Or disable and re-enable in preferences
3. Test your changes in Edit Mode with a mesh object
4. Check the Blender console for errors (Window → Toggle System Console on Windows)

---

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) guidelines
- Use 4 spaces for indentation (not tabs)
- Maximum line length: 100 characters
- Use descriptive variable names

### Blender API Conventions

```python
# Good
class MESH_OT_my_operator(Operator):
    """My operator description"""
    bl_idname = "mesh.my_operator"
    bl_label = "My Operator"
    bl_options = {'REGISTER', 'UNDO'}

# Use proper naming:
# - Operators: CATEGORY_OT_name
# - Panels: CATEGORY_PT_name
# - UI Lists: CATEGORY_UL_name
```

### Documentation

- Add docstrings to classes and complex functions
- Use inline comments for complex logic
- Keep comments up to date with code changes

### Code Organization

The main file structure:

```
mesh_annotation_layers/
    __init__.py          # Main addon file
    
Structure within __init__.py:
1. bl_info dictionary
2. Imports
3. Data Structures (PropertyGroups)
4. Operators
5. UI Lists
6. Panels
7. Draw handlers
8. Registration
```

---

## Commit Guidelines

### Commit Messages

Use clear, descriptive commit messages:

```bash
# Good
git commit -m "Add vertex selection highlight feature"
git commit -m "Fix overlay not updating after undo"
git commit -m "Update documentation for layer visibility"

# Bad
git commit -m "fix"
git commit -m "update"
git commit -m "changes"
```

### Commit Message Format

```
<type>: <subject>

<body (optional)>

<footer (optional)>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat: Add layer export functionality

- Implement JSON export for layer data
- Add import functionality
- Update UI with export/import buttons

Closes #42
```

---

## Pull Request Process

### Before Submitting

1. **Test Thoroughly**
   - Test on your target Blender version
   - Test edge cases
   - Ensure no console errors

2. **Check Code Quality**
   - No syntax errors
   - Follows coding standards
   - Proper error handling

3. **Update Documentation**
   - Update README.md if needed
   - Add to CHANGELOG.md
   - Update FAQ.md for user-facing changes

### Submitting a Pull Request

1. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request on GitHub**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template

3. **PR Title Format**
   ```
   [Type] Brief description
   
   Examples:
   [Feature] Add layer grouping functionality
   [Fix] Resolve overlay rendering issue in Blender 4.0
   [Docs] Update installation instructions
   ```

4. **PR Description Should Include**
   - What changes were made
   - Why the changes were needed
   - How to test the changes
   - Screenshots/videos if UI changes
   - Related issue numbers

### After Submitting

- Respond to review comments
- Make requested changes
- Keep the PR updated with main branch if needed
- Be patient and respectful

---

## Reporting Bugs

### Before Reporting

1. Check existing issues for duplicates
2. Test with the latest version
3. Test with a clean Blender installation
4. Gather necessary information

### Bug Report Template

```markdown
**Blender Version:** 3.6.0
**Addon Version:** 1.1.1
**Operating System:** Windows 10

**Description:**
Brief description of the bug

**Steps to Reproduce:**
1. Open Blender
2. Add a cube
3. Enter Edit Mode
4. ...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Screenshots/Videos:**
(if applicable)

**Console Errors:**
(copy from Blender console)

**Additional Context:**
Any other relevant information
```

---

## Suggesting Features

### Feature Request Template

```markdown
**Feature Name:** Layer Grouping

**Problem it Solves:**
When working with many layers, it becomes difficult to organize them.

**Proposed Solution:**
Add ability to create layer groups that can be collapsed/expanded.

**Alternative Solutions:**
- Layer filtering
- Layer search

**Additional Context:**
Similar to how Photoshop handles layer groups.

**Mockups/Examples:**
(if available)
```

### Feature Evaluation Criteria

Features are evaluated based on:
- Usefulness to users
- Implementation complexity
- Maintenance burden
- Compatibility with existing features
- Alignment with addon goals

---

## Development Guidelines

### Adding New Features

1. Discuss in an issue first (for major features)
2. Keep features focused and modular
3. Maintain backward compatibility
4. Add appropriate error handling
5. Update documentation

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] No Blender console errors
- [ ] Works in Edit Mode
- [ ] Handles edge cases gracefully
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages are clear

### Performance Considerations

- Avoid operations in draw handlers
- Use bmesh efficiently
- Cache when possible
- Test with large meshes (100k+ faces)
- Profile if adding complex features

---

## Translation Contributions

We welcome translations of documentation!

### How to Translate

1. Copy existing documentation file
2. Translate to your language
3. Keep formatting and structure
4. Submit via pull request

Example:
- `README.md` → `README.zh-CN.md` (Chinese)
- `FAQ.md` → `FAQ.ja.md` (Japanese)

---

## Getting Help

Need help contributing?

- Open a discussion on GitHub
- Ask in the issues section
- Check existing documentation
- Look at existing code for examples

---

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md (if we create one)
- Mentioned in release notes
- Part of the project's growth and success

---

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.

---

Thank you for contributing to Mesh Annotation Layers! Your efforts help make this addon better for everyone.
