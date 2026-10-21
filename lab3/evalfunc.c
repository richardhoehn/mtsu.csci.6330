#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

static int first_time = 1;
static int answerids[4] = {-1,-1,-1,-1};
static int max_nodeids = 1023;
static double fake_work_time = 0.005;


static double timestamp()
{
    struct timeval tv;

    gettimeofday( &tv, ( struct timezone * ) 0 );
    return ( tv.tv_sec + (tv.tv_usec / 1000000.0) );
}

double evalfunc(int nodeid, int *expandid1, int *expandid2)
{
    int i;
    char *str, *token, *answerids_str, *endptr;
    double rc, stime;

    if (first_time)
    {
        setbuf(stdout,NULL);
        first_time = 0;
        str = getenv("EVALFUNC_MAXNODEIDS");
        if (str)
        {
            max_nodeids = atoi(str);
        }
        str = getenv("EVALFUNC_FAKEWORKTIME");
        if (str)
        {
            fake_work_time = strtod(str, &endptr);
        }
        str = getenv("EVALFUNC_ANSWERIDS");
        if (str)
        {
            answerids_str = strdup(str);
            printf("evalfunc: ANSIDS %s\n",answerids_str);
            i = 0;
            while ( (token = strsep(&answerids_str,",")) )
                answerids[i++] = atoi(token);
        }
        printf("evalfunc:  maxnodeids %d  fakeworktime %f  answerids %d %d %d %d\n",
               max_nodeids,fake_work_time,answerids[0],answerids[1],answerids[2],answerids[3]);
    }

    if (nodeid > max_nodeids)
    {
        *expandid1 = -1;
        *expandid2 = -1;
        return 0.0;
    }

    *expandid1 = (nodeid * 2) + 1;  // lhs
    if (*expandid1 > max_nodeids)
        *expandid1 = -1;
    *expandid2 = (nodeid * 2) + 2;  // rhs
    if (*expandid2 > max_nodeids)
        *expandid2 = -1;

    rc = (1.0 / (double)(nodeid+1));  // default; may chg below; +1 avoid divide by 0
    for (i=0; i < 4; i++)
    {
        if (nodeid == answerids[i])
        {
            if (nodeid == 0  ||  nodeid == 1)  // permit 0 and 1 to be solutions also
                rc = 1.1;
            else
                rc = (double) nodeid;
        }
    }

    // do fake work
    stime = timestamp();
    while ( (timestamp() - stime) < fake_work_time)
        ;
    
    return rc;
}
