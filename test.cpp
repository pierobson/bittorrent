#include "test.hpp"


using namespace std;


/*class Test {
	public:
		Test(std::vector<struct the> ar);
		string ToString();
	private:
		vector<struct the> b;
};*/

Test::Test(vector<struct the> ar)
{
	b = ar;
}

string Test::ToString()
{
	string out = "";
	for (struct the t : b) {
		out += to_string(t.bill) + " : " + to_string(t.ted) + "\n";
	}
	return out;
}

int main() {
	std::vector<struct the> vec(10);

	for (int i=0; i<10; i++) {
		struct the t;
		t.bill = i;
		t.ted = i+1;
		vec[i] = t;
	}

	Test test(vec);
	cout << test.ToString() << endl << endl;
	for (struct the c : vec) {
		cout << to_string(c.bill) + " : " + to_string(c.ted) << endl;
	}
}
