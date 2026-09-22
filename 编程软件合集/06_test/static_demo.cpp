#include <cstdio>
int factorial(int n) {
    int acc = 1;
    for (int i = 1; i <= n; ++i) acc *= i;
    return acc;
}
int main() {
    int n = 5;
    int r = factorial(n);
    printf("fact(%d)=%d\n", n, r);
    return 0;
}
