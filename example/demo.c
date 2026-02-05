#include <stdio.h>
#include <string.h>

int main() {
    char input[64];
    const char* secret = "antigravity_secret_123";

    printf("Enter the license key: ");
    if (fgets(input, sizeof(input), stdin)) {

		input[strcspn(input, "\n")] = 0;

        if (strcmp(input, secret) == 0) {
            printf("Access Granted! You solved it.\n");
        } else {
            printf("Access Denied! Try again.\n");
        }
    }

    return 0;
}