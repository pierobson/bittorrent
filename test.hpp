#include <stdlib.h>
#include <string>
#include <vector>
#include <iostream>

struct the {
	int bill;
	int ted;
};

class Test {
	public:
		Test(std::vector<struct the> ar);
		std::string ToString();
	private:
		std::vector<struct the> b;
};
