#include <iostream>
#include <vector>
#include <string>
#include <algorithm>

using namespace std;

// Returns the sum of all numbers in the vector
int sumOf(const vector<int>& nums) {
    int total = 0;
    for (size_t i = 0; i < nums.size(); i++) {
        total += nums[i];
    }
    return total;
}

// Returns the average of the numbers (0 if empty)
double averageOf(const vector<int>& nums) {
    if (nums.empty()) {
        return 0.0;
    }
    return static_cast<double>(sumOf(nums)) / nums.size();
}

// Returns the largest number in the vector
int maxOf(const vector<int>& nums) {
    int best = nums[0];
    for (size_t i = 1; i < nums.size(); i++) {
        if (nums[i] > best) {
            best = nums[i];
        }
    }
    return best;
}

// Returns n! (factorial)
long long factorial(int n) {
    long long result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

// Returns true if n is prime
bool isPrime(int n) {
    if (n < 2) {
        return false;
    }
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) {
            return false;
        }
    }
    return true;
}

// Returns the string reversed
string reverseString(const string& s) {
    string result = s;
    reverse(result.begin(), result.end());
    return result;
}

// Returns true if the string reads the same forwards and backwards
bool isPalindrome(const string& s) {
    int left = 0;
    int right = static_cast<int>(s.size()) - 1;
    while (left < right) {
        if (s[left] != s[right]) {
            return false;
        }
        left++;
        right--;
    }
    return true;
}

// Returns the n-th Fibonacci number (fib(0)=0, fib(1)=1)
long long fibonacci(int n) {
    
long long a = 0, b = 1;
    if (n == 0) return 0;
    for (int i = 2; i <= n; i++) {
        a = b;
        b = a + b;
    }
    return a;






}

int main() {
    vector<int> nums = {4, 8, 15, 16, 23, 42};

    cout << "Numbers: ";
    for (int n : nums) {
        cout << n << " ";
    }
    cout << endl;

    cout << "Sum: " << sumOf(nums) << endl;
    cout << "Average: " << averageOf(nums) << endl;
    cout << "Max: " << maxOf(nums) << endl;

    cout << "Factorial of 5: " << factorial(5) << endl;
    cout << "Is 17 prime? " << (isPrime(17) ? "yes" : "no") << endl;
    cout << "Is 18 prime? " << (isPrime(18) ? "yes" : "no") << endl;

    cout << "Reverse of 'hello': " << reverseString("hello") << endl;
    cout << "Is 'racecar' a palindrome? " << (isPalindrome("racecar") ? "yes" : "no") << endl;
    cout << "Is 'hello' a palindrome? " << (isPalindrome("hello") ? "yes" : "no") << endl;

    cout << "Fibonacci(-10): " << fibonacci(-10) << endl;

    return 0;
}