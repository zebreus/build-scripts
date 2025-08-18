output_file=$(mktemp)

PYTHON_PACKAGE=${1:-"python-with-packages"}

for testfile in tests/*.py; do
    # Extract just the filename without path
    TEST_NAME=$(basename "$testfile")

    # Skip test if it is a *.skip.py file
    if [[ "$TEST_NAME" == *.skip.py ]]; then
        echo -e "\033[0;33mSkipping:\033[0m \033[1m$TEST_NAME\033[0m"
        continue
    fi
    
    
    # Print colorful running message
    echo -e "\033[0;34m▶ Running:\033[0m \033[1m$TEST_NAME\033[0m"
    
    # Run the test
    $WASMER run --net --mapdir="/src:$(pwd)" --llvm $PYTHON_PACKAGE /src/$testfile
    EXIT_CODE=$?
    
    # Check result and print colorful outcome
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "  \033[0;32m✓ PASSED\033[0m $TEST_NAME" | tee -a "$output_file"
    else
        echo -e "  \033[0;31m✗ FAILED\033[0m $TEST_NAME" | tee -a "$output_file"
        echo -e "  \033[0;31m└── Test failed with exit code $EXIT_CODE\033[0m" | tee -a "$output_file"
    fi
    echo ""
done
# Print summary
cat "$output_file"
echo ""
echo -e "\033[1;34mSummary:\033[0m"
if grep -q "✗ FAILED" "$output_file"; then
    echo -e "  \033[0;31mSome tests failed."
else
    echo -e "  \033[0;32mAll tests passed successfully!\033[0m"
fi
