# Contributing to Brussels Food Map

Thank you for your interest in contributing to Brussels Food Map!

## Ways to Contribute

### Report Issues

Found a bug or have a suggestion? Open an issue on GitHub with:
- Clear description of the problem or suggestion
- Steps to reproduce (for bugs)
- Screenshots if applicable

### Restaurant Data Corrections

If you notice incorrect restaurant data:
- **Wrong category**: A shop listed as a restaurant, or vice versa
- **Closed permanently**: Restaurant no longer exists
- **Wrong location**: Coordinates are off

Please open an issue with the restaurant name and the correction needed.

### Algorithm Improvements

Ideas for improving the ranking algorithm are welcome! Consider:
- New signals that indicate quality (with data sources)
- Adjustments to existing weights
- Brussels-specific knowledge we're missing

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-improvement`)
3. Make your changes
4. Test locally (`python src/app.py`)
5. Commit with clear messages
6. Open a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/brussels-food-map.git
cd brussels-food-map

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python src/app.py
```

## Code Style

- Python: Follow PEP 8
- JavaScript: Use consistent formatting (the project uses vanilla JS)
- Comments: Explain *why*, not *what*

## Questions?

Open an issue with the "question" label.
