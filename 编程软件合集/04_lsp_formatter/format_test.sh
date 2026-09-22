#!/usr/bin/env bash
# clang-format 实测 A/B：证明它真改了东西（用字节数对比）
cat > /tmp/fmt_in.cpp <<'CPP'
int main( ) {
std::vector<int> v{1,2,3};
for(auto i:v){std::cout<<i;}
}
CPP
BEFORE=$(stat -c%s /tmp/fmt_in.cpp)
clang-format /tmp/fmt_in.cpp > /tmp/fmt_out.cpp
AFTER=$(stat -c%s /tmp/fmt_out.cpp)
echo "格式化前: $BEFORE bytes"
echo "格式化后: $AFTER bytes"
[ "$BEFORE" != "$AFTER" ] && echo "✅ 内容真变了" || echo "❌ 没变化"
cat /tmp/fmt_out.cpp
