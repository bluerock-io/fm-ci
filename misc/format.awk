BEGIN { printf "%-30s\t %s\t %-5s\t %-5s\t %-5s\r\n", " ","real", "user", "sys","mem"; }
{
    split($0, a, ",");
    split(a[1], real, ":");
    split(a[2], user, ":");
    split(a[3], sys, ":");
    split(a[4], mem, " ");
    split($0, name, " ");
    if (length(name[1]) > 28) {
        name_trunc = substr( name[1], length(name[1]) - 28, length(name[1]));
    } else {
        name_trunc = name[1];
    }
    printf "%-30s\t %.2fs\t %.2fs\t %.2fs\t %d ko\r\n", name_trunc,real[2],user[2],sys[2],mem[2]
}
