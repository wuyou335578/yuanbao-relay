#include <iostream>
#include <vector>
#include <string>

int compute(int n) {
    int total = 0;
    std::string tag = "sum";
    std::vector<int> data;
    for (int i = 1; i <= n; ++i) {
        data.push_back(i);
        total += i;
    }
    return total;
}

int main() {
    int n = 5;
    int result = compute(n);
    std::cout << "result=" << result << std::endl;
    return 0;
}
