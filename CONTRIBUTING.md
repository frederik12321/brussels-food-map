# Contributing to Local Food Map

Thank you for your interest in contributing! This project welcomes contributions of all kinds.

## Ways to Contribute

### 🌍 Adapt for Your City

The most impactful contribution is adapting this for your own city:

1. **Fork the repository**
2. **Copy the city template**: `cp config/city_template.py config/your_city_config.py`
3. **Fill in your city's data**:
   - District/neighborhood boundaries and classifications
   - Local food streets where locals eat
   - Tourist trap zones
   - Michelin and local guide data
   - Chain restaurant patterns
   - Reddit/local forum subreddit
4. **Document your data sources** in your PR
5. **Share your deployment** in the Issues!

### 🐛 Report Bugs

Found a bug? Please open an issue with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable

### 💡 Suggest Features

Have an idea? Open an issue with:
- Description of the feature
- Use case / why it would be useful
- Any implementation ideas

### 🔧 Submit Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests if available
5. Commit: `git commit -m "Add your feature"`
6. Push: `git push origin feature/your-feature`
7. Open a Pull Request

## Code Guidelines

### Python

- Follow PEP 8 style guide
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

### Commits

- Use clear, descriptive commit messages
- Reference issues when applicable: "Fix #123"
- Keep commits focused on single changes

### City Configurations

When adding a new city:
- Use the template in `config/city_template.py`
- Include comments explaining data sources
- Test the full pipeline before submitting
- Document any city-specific quirks

## City-Specific Data Sources

When researching your city, consider:

- **Districts/Neighborhoods**: Wikipedia, local government sites
- **Tourist Zones**: Travel guides, TripAdvisor "most visited"
- **Diaspora Hubs**: Local news, community organization sites
- **Michelin Stars**: Official Michelin Guide
- **Local Guides**: TimeOut, Eater, local food blogs
- **Reddit**: Check r/[yourcity] for food recommendations

## Questions?

- Open an issue for questions
- Check existing issues first
- Be patient and respectful

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
