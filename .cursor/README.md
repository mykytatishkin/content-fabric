# .cursor Directory

This directory contains configuration and documentation files for Cursor AI to better understand the project structure, architecture, and development patterns.

## 📁 Files Overview

### `rules` - Main AI Assistant Rules
**Purpose**: Comprehensive guidelines for AI assistant when working with this codebase

**Contains**:
- Project overview and capabilities
- Architecture explanation
- Code style and conventions
- Development workflows
- Security considerations
- Testing guidelines
- Common patterns and best practices

**When to update**: When major architectural changes are made, new features added, or coding standards change

---

### `context.md` - Project Context
**Purpose**: High-level understanding of what the project is and how it works

**Contains**:
- "What is this project?" explanation
- Three-layer architecture overview
- Data flow diagrams (ASCII)
- Key components descriptions
- Current state and recent changes
- Development workflow examples
- Domain knowledge

**When to update**: When adding new major features, changing architecture, or completing milestones

---

### `architecture.md` - Technical Architecture
**Purpose**: Deep technical details and system design documentation

**Contains**:
- Detailed system architecture diagrams
- Complete data flow diagrams
- Database schemas (SQL)
- API integration details
- Component dependency trees
- Security considerations
- Performance optimizations
- Monitoring and logging setup
- Deployment checklist

**When to update**: When changing system design, adding new integrations, or modifying database schema

---

### `quick-reference.md` - Quick Reference Guide
**Purpose**: Fast access to common commands, code snippets, and patterns

**Contains**:
- Most common CLI commands
- Code snippets for frequent operations
- Configuration examples
- Common patterns (error handling, batch processing, etc.)
- Troubleshooting quick fixes
- Useful links

**When to update**: When adding new commands, discovering useful patterns, or changing APIs

---

## 🎯 How to Use

### For AI Assistant (Cursor)
These files are automatically loaded by Cursor AI to provide context about the project. The AI uses this information to:
- Better understand code structure
- Suggest appropriate patterns and solutions
- Follow project conventions
- Generate contextually relevant code
- Provide accurate help and explanations

### For Developers
You can read these files to:
- Understand project architecture quickly
- Find code examples and patterns
- Look up common commands
- Learn about data flows and system design
- Onboard new team members

## 📝 Maintenance

### When to Update

| File | Update Frequency | Trigger Events |
|------|-----------------|----------------|
| `rules` | Monthly | Architecture changes, new patterns |
| `context.md` | Bi-weekly | New features, milestones |
| `architecture.md` | Monthly | System design changes, new integrations |
| `quick-reference.md` | Weekly | New commands, useful patterns |

### Update Checklist

When making significant changes to the project:

- [ ] Update relevant `.cursor` files
- [ ] Check if code examples are still valid
- [ ] Update diagrams if architecture changed
- [ ] Add new commands to quick reference
- [ ] Update version and last updated date
- [ ] Review all files for outdated information

## 🔍 File Relationships

```
.cursor/
├── rules                    # ← Main guidelines (read this first)
│   ↓
├── context.md              # ← High-level understanding
│   ↓
├── architecture.md         # ← Deep technical details
│   ↓
└── quick-reference.md      # ← Quick lookup reference
```

## 📚 Additional Resources

### Root-level Documentation
- `README.md` - User-facing README
- `DOCS_INDEX.md` - Complete documentation index
- `PROJECT_STRUCTURE.md` - File structure explanation

### In-depth Guides
- `docs/guides/` - User guides and tutorials
- `docs/parallel/` - Parallel processing documentation
- `docs/technical/` - Technical documentation

### Examples
- `examples/` - Code examples
- `test_*.py` - Test files with usage examples

## 🚀 Quick Start for New Contributors

1. **Read**: `.cursor/rules` (understand project conventions)
2. **Explore**: `.cursor/context.md` (grasp overall architecture)
3. **Deep Dive**: `.cursor/architecture.md` (technical details)
4. **Reference**: `.cursor/quick-reference.md` (bookmark for quick lookups)

## ⚙️ Configuration

### `.cursorrules` (Root Level)
- Shorter version of `rules` for quick reference
- Used by some AI tools as fallback
- Keep in sync with `.cursor/rules`

### `.cursorignore` (Root Level)
- Similar to `.gitignore` but for Cursor indexing
- Excludes large files, media, models from indexing
- Improves performance and reduces noise

## 🔄 Version Control

### Current Version
All `.cursor` files are at **version 1.0** as of **2025-10-13**

### Change Log
- **2025-10-13**: Initial creation with comprehensive documentation
- **2025-10-13**: Added parallel voice processing details
- **2025-10-13**: Documented task management system

### Versioning
Update version numbers in file footers when making significant changes:
```markdown
**Version**: 1.1  
**Last Updated**: YYYY-MM-DD
```

## 💡 Tips

### For AI Assistant Context
- Keep files under 1000 lines for optimal parsing
- Use clear section headers with emojis for easy navigation
- Include both high-level concepts and specific code examples
- Update regularly to reflect current state

### For Developer Use
- Bookmark `quick-reference.md` for daily use
- Refer to `architecture.md` when designing new features
- Use code snippets from files as templates
- Keep context files open when onboarding new team members

## 🐛 Troubleshooting

### Cursor AI not following conventions?
- Check if `.cursor/rules` is up to date
- Ensure file is properly formatted (markdown)
- Verify no syntax errors in code examples

### Outdated information in responses?
- Update relevant `.cursor` files
- Increment version numbers
- Clear Cursor cache if needed

### Missing context for specific feature?
- Add to appropriate file (`rules`, `context`, or `architecture`)
- Include code examples in `quick-reference.md`
- Update related documentation in `docs/`

## 📧 Questions?

If you have questions about:
- **Project structure**: See `.cursor/context.md`
- **How to implement feature**: See `.cursor/rules` and `quick-reference.md`
- **System design**: See `.cursor/architecture.md`
- **Specific API**: Check `docs/guides/`

---

**Maintained by**: Development Team  
**Last Major Update**: 2025-10-13  
**Status**: Active and regularly updated

