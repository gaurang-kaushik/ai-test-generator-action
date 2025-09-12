# AI Test Generator Action

A GitHub Action that automatically generates high-quality JUnit5 + Mockito test classes for Java code using Google's Gemini AI and enforces code coverage thresholds.

## 🚀 Features

- **AI-Powered Test Generation**: Uses Google Gemini AI to generate comprehensive test cases
- **Coverage Enforcement**: Automatically enforces code coverage thresholds (default 80%)
- **Iterative Improvement**: Keeps generating tests until coverage threshold is met
- **Quality Assurance**: Only accepts tests that compile and pass
- **Maven Integration**: Works with Maven projects and JaCoCo coverage

## 📖 Usage

### Basic Usage

```yaml
name: AI Test Generator
on: [pull_request, push]

jobs:
  generate-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - uses: your-username/ai-test-generator-action@v1
        with:
          api-key: ${{ secrets.GOOGLE_API_KEY }}
          coverage-threshold: '80'
          source-path: 'src/main/java'
          test-path: 'src/test/java'
```

### Advanced Configuration

```yaml
- uses: your-username/ai-test-generator-action@v1
  with:
    api-key: ${{ secrets.GOOGLE_API_KEY }}
    coverage-threshold: '90'
    source-path: 'app/src/main/java'
    test-path: 'app/src/test/java'
    model: 'gemini-1.5-flash'
    auto-commit: 'true'
```

## ⚙️ Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `api-key` | Google API key for Gemini AI | Yes | - |
| `coverage-threshold` | Minimum code coverage threshold (percentage) | No | `80` |
| `source-path` | Path to Java source files relative to repository root | No | `src/main/java` |
| `test-path` | Path for generated test files relative to repository root | No | `src/test/java` |
| `model` | AI model to use for test generation | No | `gemini-1.5-pro` |
| `auto-commit` | Whether to automatically commit generated tests | No | `false` |

## 🔧 Setup

### 1. Create a GitHub Repository

Create a new repository for this action (e.g., `ai-test-generator-action`).

### 2. Copy Files

Copy all files from this repository to your new repository.

### 3. Publish the Action

The action is ready to use! Other repositories can reference it using:

```yaml
uses: your-username/ai-test-generator-action@v1
```

## 📊 How It Works

1. **Detection**: Identifies changed Java files in your pull request
2. **Generation**: Uses AI to generate comprehensive test cases
3. **Validation**: Ensures generated tests compile and pass
4. **Coverage**: Measures code coverage using JaCoCo
5. **Iteration**: Generates more tests if coverage is below threshold
6. **Enforcement**: Fails the PR if coverage target isn't met

## 🎯 Sample Output

The action generates tests like this:

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {
    
    @Mock
    private OrderRepository orderRepository;
    
    @Mock
    private RestTemplate restTemplate;
    
    @InjectMocks
    private OrderService orderService;
    
    @Test
    void processOrder_ValidInput_ReturnsSuccess() {
        // Test implementation
    }
    
    @Test
    void processOrder_NullOrderId_ThrowsException() {
        // Test implementation
    }
    
    // More test cases...
}
```

## 🔍 Troubleshooting

### Common Issues

1. **Coverage 0.0%**: Check that source/test paths are correct
2. **Tests not generating**: Verify Google API key is set
3. **Tests failing**: System auto-reverts failing tests
4. **JaCoCo issues**: Ensure Maven configuration is correct

### Debug Steps

1. Check GitHub Actions logs
2. Verify file paths and structure
3. Test API key with manual generation
4. Review generated test quality

## 📈 Success Metrics

- **Coverage Improvement**: Can reach 80%+ from 0% in 3-6 iterations
- **Test Quality**: Comprehensive coverage of happy paths, edge cases, exceptions
- **Reliability**: Only accepts working, compilable tests
- **Automation**: No manual intervention required

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Create a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

For issues or questions:
1. Check the GitHub Actions logs
2. Review the documentation
3. Open an issue in this repository
